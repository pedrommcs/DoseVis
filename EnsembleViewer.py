# EnsembleViewer by Pedro Silva
#
# Based on SkeletonAUIViewer:
# Copyright (c) Charl P. Botha, TU Delft.
# All rights reserved.
# See COPYRIGHT for details.

# Inspired by: 
#	- EmphysemaViewer by Corine Slagboom & Noeska Smit
#	- DosePlanningViewer by Renata Raidou
#	- multiDirectionalSlicedViewSegmentation3dVieWeR by Ralf Nieuwenhuizen & Jan-Willem van Velzen

from __future__ import division

# set to False for 3D viewer, True for 2D image viewer
IMAGE_VIEWER = True

# import the frame, i.e. the wx window containing everything
import EnsembleViewerFrame
# and do a reload, so that the GUI is also updated at reloads of this
# module.
reload(EnsembleViewerFrame)

from module_kits.misc_kit import misc_utils
from module_base import ModuleBase
from module_mixins import IntrospectModuleMixin
from comedi_utils import CMSliceViewer
from comedi_utils import SyncSliceViewers
from isovalue_utils import Isovalue
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas

#from interactors import MouseInteractorHighLightActor
from selectors import SelectFromCollection
from itertools import product
from itertools import chain
import module_utils
import os
import time
import sys
import traceback
import vtk
import wx
import re
import collections
import operator
from operator import itemgetter
from vtk.util import numpy_support
import numpy as np
import seaborn as sns
import pandas as pd
import csv
import matplotlib
import random
from random import randint
import pickle
from matplotlib.widgets import LassoSelector
from matplotlib.path import Path
from mpldatacursor import datacursor
import matplotlib.patches as mpatches
import wx.lib.agw.ultimatelistctrl as ulc
import wx.lib.colourselect as csel
import wx.lib.agw.floatspin as fs

class EnsembleViewer(IntrospectModuleMixin, ModuleBase):

    def __init__(self, module_manager):
        """Standard constructor.  All DeVIDE modules have these, we do
        the required setup actions.
        """
		# we record the setting here, in case the user changes it
        # during the lifetime of this model, leading to different
        # states at init and shutdown.
        self.IMAGE_VIEWER = IMAGE_VIEWER

        ModuleBase.__init__(self, module_manager)

        # create the view frame
        self._view_frame = module_utils.instantiate_module_view_frame(
            self, self._module_manager,
            EnsembleViewerFrame.EnsembleViewerFrame)
			
        # change the title of the frame 
        self._view_frame.SetTitle('DoseVis')
		
		#This interactor style disables 3D operations such as Rotate and Scroll through slices.
        #style = vtk.vtkInteractorStyleImage()
		
		#Create the renderer for the axial view
        self.renA = vtk.vtkRenderer()
        self.renA.SetBackground(0.5,0.5,0.5)
        self._view_frame.axial.GetRenderWindow().AddRenderer(self.renA)
        self.slice_viewerA = CMSliceViewer(self._view_frame.axial, self.renA)
        #self._view_frame.axial.SetInteractorStyle(style)

		#Create the renderer for the coronal view
        self.renC = vtk.vtkRenderer()
        self.renC.SetBackground(0.5,0.5,0.5)
        self._view_frame.coronal.GetRenderWindow().AddRenderer(self.renC)
        self.slice_viewerC = CMSliceViewer(self._view_frame.coronal, self.renC)

		#Create the renderer for the saggital view
        self.renS = vtk.vtkRenderer()
        self.renS.SetBackground(0.5,0.5,0.5)
        self._view_frame.sagittal.GetRenderWindow().AddRenderer(self.renS)
        self.slice_viewerS = CMSliceViewer(self._view_frame.sagittal, self.renS)

		# Create the Renderer for the Volume Rendering
        self.ren_iso = vtk.vtkRenderer()
        self.ren_iso.SetBackground(0.5,0.5,0.5)
        self._view_frame.interactor3d.GetRenderWindow().AddRenderer(self.ren_iso)
		
        # Set a better camera position
        self.camera = vtk.vtkCamera()
        self.camera.SetViewUp(0, 0, -1)
        self.camera.SetPosition(-2, -2, -2)

        self._view_frame.interactor3d._orientation_widget.On()  
		
		#Create a text property
        text = vtk.vtkTextProperty()
        text.SetColor(0,0,0)
        text.BoldOn()
        text.SetOpacity(1.0)
		
		# Create the widget
        self.balloonRep = vtk.vtkBalloonRepresentation()
        self.balloonRep.SetBalloonLayoutToImageRight()
        self.balloonRep.SetTextProperty(text)
 
        self.balloon_axial = vtk.vtkBalloonWidget()
        self.balloon_axial.SetInteractor(self._view_frame.axial)
        self.balloon_axial.SetRepresentation(self.balloonRep)
		
        self.balloon_sagittal = vtk.vtkBalloonWidget()
        self.balloon_sagittal.SetInteractor(self._view_frame.sagittal)
        self.balloon_sagittal.SetRepresentation(self.balloonRep)
		
        self.balloon_coronal = vtk.vtkBalloonWidget()
        self.balloon_coronal.SetInteractor(self._view_frame.coronal)
        self.balloon_coronal.SetRepresentation(self.balloonRep)
		
		######################## Create opacity and color transfer functions for 3D View ####################
		
        self.otf_3d = vtk.vtkPiecewiseFunction()
        self.otf_3d.AddPoint(0, 0)
        self.otf_3d.AddPoint(100, 1)

        self.ctf_3d = vtk.vtkColorTransferFunction()
        self.ctf_3d.AddRGBPoint(0, 1, 1, 0) # yellow
        self.ctf_3d.AddRGBPoint(120, 1, 1, 0) # yellow
		
		################### Setup the volume pipeline ####################
		
		#Set the functions.
        self.volProp = vtk.vtkVolumeProperty()
        self.volProp.SetColor(self.ctf_3d)
        self.volProp.SetScalarOpacity(self.otf_3d)
        self.volProp.ShadeOn()
        self.volProp.SetAmbient(0.5)
        self.volProp.SetDiffuse(0.9)
        #self.volProp.SetInterpolationTypeToLinear()
		
		#Use an VolumeRayCastCompositeFunction() to compute the intensity.
        self.comp = vtk.vtkVolumeRayCastCompositeFunction()
        self.volMapper = vtk.vtkVolumeRayCastMapper()
        self.volMapper.SetVolumeRayCastFunction(self.comp )
		#Set the sample distance
        self.volMapper.SetSampleDistance(.5)

		#Create a Volume and set the Mapper.
        self.vol = vtk.vtkVolume()
        self.vol.SetMapper(self.volMapper)
        self.vol.SetProperty(self.volProp)

		###################### Setup the isosurface pipeline ################
        self.surf = vtk.vtkContourFilter()
        self.surf.SetValue(0,30)

        sil = vtk.vtkPolyDataSilhouette()
        sil.SetInput(self.surf.GetOutput())
        sil.SetCamera(self.ren_iso.GetActiveCamera())
        sil.SetEnableFeatureAngle(0)

        self.silh_mapper = vtk.vtkPolyDataMapper()
        self.silh_mapper.SetInput(sil.GetOutput())
        #self.silh_mapper.Update()
		
        self.silh_actor = vtk.vtkActor()
        self.silh_actor.SetMapper(self.silh_mapper)
        self.silh_actor.GetProperty().SetColor(0, 0, 0)
        self.silh_actor.GetProperty().SetLineWidth(3)
		
        self.surfMapper = vtk.vtkPolyDataMapper()
        self.surfMapper.SetInput(self.surf.GetOutput())
        self.surfMapper.ScalarVisibilityOff()
        #self.surfMapper.Update()
		
        self.surf_actor = vtk.vtkActor()
        self.surf_actor.SetMapper(self.surfMapper)
        self.surf_actor.GetProperty().SetColor(1,1,1)
        self.surf_actor.GetProperty().SetOpacity(float(65) / 100)
		
		###################### Setup the contour initialization####################
        self.contourlist = []
		
        #self.dic_contour_actors = {}
		
        self.xmin = 0
        self.xmax = 0
        self.ymin = 0
        self.ymax = 0
		
        self.doseplans = {}		
		
        self.isovalues_barplot = []
        self.band_depths = []
		
        self.indexes = []
        self.dic_iso_to_index = {}
		
        self.contours_info = {}
		
		
        self.isoline_sliders = {}
        self.isoline_spins = {}
        self.colors = {}	
        self.options = {}
        self.actives = {}
		
        self.checkboxes_doseplans = {}
		
        self.isovalue_objs = []
		
		
        self.extract = vtk.vtkExtractVOI()
		
        self.show_contours_boolean = False
        self.show_boxplot_boolean = False		
		
		
        self.isovalues = {}
        self.median_outliers_ids = {}
		
        self.image_data50 = {}
        self.image_data100 = {}		
		
        self.isovalue = 60
		
        self.planlist = []
		
		
        self.barplot_data = {}
		
        self.active = {}
		
        self.ctf_isosurface = vtk.vtkColorTransferFunction()
        self.ctf_isosurface.SetColorSpaceToRGB()
        self.ctf_isosurface.AddRGBPoint(0, 0, 0, 1) # blue
        self.ctf_isosurface.AddRGBPoint(100, 1, 0, 0) # red
		
		#Yellow Opacities
        self.ctf_yellow = vtk.vtkColorTransferFunction()
        self.ctf_yellow.SetColorSpaceToRGB()
        self.ctf_yellow.AddRGBPoint(0,1,1,0) 
        self.ctf_yellow.AddRGBPoint(1,1,1,0)
				
		# Red Opacities
        self.ctf_red = vtk.vtkColorTransferFunction()
        self.ctf_red.SetColorSpaceToRGB()
        self.ctf_red.AddRGBPoint(0,1,0,0) 
        self.ctf_red.AddRGBPoint(1,1,0,0)
		
		# Blue Opacities
        self.ctf_blue = vtk.vtkColorTransferFunction()
        self.ctf_blue.SetColorSpaceToRGB()
        self.ctf_blue.AddRGBPoint(0,0,0.643,0.941) 
        self.ctf_blue.AddRGBPoint(1,0,0.643,0.941)
		
        self.otf = vtk.vtkPiecewiseFunction()
        self.otf.AddPoint(0, 0.3)
        self.otf.AddPoint(1, 0.8)
		

        self.scBar_mean = vtk.vtkScalarBarActor()
        self.scBar_std = vtk.vtkScalarBarActor()
		
        self.scBar3d = vtk.vtkScalarBarActor()
        self.scBarWidget = vtk.vtkScalarBarWidget()
		
        self.mindata = None
        self.maxdata = None
        self.diffdata = None

        self.gridsize1 = 30
        self.gridsize2 = 30
        self.gridsize3 = 30

        self.overep = None
		
        self.item = None
		
        self.meanx = []
        self.stdy = []
		
        self.count = 0
		
        self.radio_id = 9
		
        self.ctf50 = vtk.vtkColorTransferFunction()
        self.ctf50.AddRGBPoint(0, 0, 0, 0) # lawn green
        self.ctf50.AddRGBPoint(100, 0.38,0.35,0.74) # lawn green
        self.ctf50.AddRGBPoint(255, 0.38,0.35,0.74) # lawn green	
		
        self.lut50 = vtk.vtkLookupTable()
        self.lut50.SetTableValue(0, 0, 0, 0)
        self.lut50.SetTableValue(100, 0.38,0.35,0.74)
        self.lut50.SetTableValue(255, 0.38,0.35,0.74)
        self.lut50.Build()
		
        self.sync = SyncSliceViewers()
        self.sync.add_slice_viewer(self.slice_viewerA)
        self.sync.add_slice_viewer(self.slice_viewerC)
        self.sync.add_slice_viewer(self.slice_viewerS)
		
        self.tooltip = wx.ToolTip(tip='tip with a long %s line and a newline\n' % (' '*100))
        self.x = np.array(list('XYZV'))
		
		
        self.primary_colors = [[255,255,0.0],[255,0.0,0.0],[0.0,164,240]] #yellow, red, blue
		
        self.primary_colors_float = [[1,1,0.0],[1,0.0,0.0],[0.0,0.643,0.941]]
		
        self.primary_colors_float_tuple = [(1.0,1.0,0.0,1.0),(1,0.0,0.0, 1.0),(0,0.643,0.941, 1.0)]

        self.ind = []
		
        self.lut_red = vtk.vtkLookupTable()
        self.lut_red.SetNumberOfTableValues(3)
        self.lut_red.SetTableValue(0,0,0,0,0)
        self.lut_red.SetTableValue(1, 1,0,0,1)
        self.lut_red.SetTableValue(2, 1,0,0,1)
        self.lut_red.Modified()
        self.lut_red.Build()
		
		#we set the color for the median isocontour
        self.median_purple = (1,0,0.8)
        self.median_green = (0,1,0)
        self.median_orange = (1, 0.5, 0)
        #self.median_light_blue = (0.1, 1, 1)
		
        # hook up all event handlers
        self._bind_events()

        # anything you stuff into self._config will be saved
        self._config.last_used_dir = ''

        # make our window appear (this is a viewer after all)
        self.view()
        # all modules should toggle this once they have shown their
        # views.
        self.view_initialised = True

        # apply config information to underlying logic
        self.sync_module_logic_with_config()
        # then bring it all the way up again to the view
        self.sync_module_view_with_logic()

    def close(self):
        """Clean-up method called on all DeVIDE modules when they are
        deleted.
        FIXME: Still get a nasty X error :(
        """
        vf = self._view_frame
		
        # with this complicated de-init, we make sure that VTK is
        # properly taken care of
        self.renA.RemoveAllViewProps()
        self.renC.RemoveAllViewProps()
        self.renS.RemoveAllViewProps()
        self.ren_iso.RemoveAllViewProps()

        # this finalize makes sure we don't get any strange X
        # errors when we kill the module.
        self.slice_viewerA.close()
        self.slice_viewerC.close()
        self.slice_viewerS.close()
        vf.axial.GetRenderWindow().Finalize()
        vf.axial.SetRenderWindow(None)
        vf.coronal.GetRenderWindow().Finalize()
        vf.coronal.SetRenderWindow(None)
        vf.sagittal.GetRenderWindow().Finalize()
        vf.sagittal.SetRenderWindow(None)
        vf.interactor3d.GetRenderWindow().Finalize()
        vf.interactor3d.SetRenderWindow(None)
        del vf.axial
        del vf.coronal
        del vf.sagittal
        del vf.interactor3d
        del self.slice_viewerS
        del self.slice_viewerC
        del self.slice_viewerA
		
        for object in self.isovalue_objs:
            del object
		
        del self.balloon_axial
        del self.balloon_sagittal
        del self.balloon_coronal
		
        self.count = 0
        # done with VTK de-init

        # now take care of the wx window
        vf.close()
        # then shutdown our introspection mixin
        IntrospectModuleMixin.close(self)

    def get_input_descriptions(self):
        # define this as a tuple of input descriptions if you want to
        # take input data e.g. return ('vtkPolyData', 'my kind of
        # data')
        return ()

    def get_output_descriptions(self):
        # define this as a tuple of output descriptions if you want to
        # generate output data.
        return ()

    def set_input(self, idx, input_stream):
        # this gets called right before you get executed.  take the
        # input_stream and store it so that it's available during
        # execute_module()
        pass

    def get_output(self, idx):
        # this can get called at any time when a consumer module wants
        # you output data.
        pass

    def execute_module(self):
        # when it's you turn to execute as part of a network
        # execution, this gets called.
        pass

    def logic_to_config(self):
        pass

    def config_to_logic(self):
        pass

    def config_to_view(self):
        pass

    def view_to_config(self):
        pass

    def view(self):
        self._view_frame.Show()
        self._view_frame.Raise()

        # because we have an RWI involved, we have to do this
        # SafeYield, so that the window does actually appear before we
        # call the render.  If we don't do this, we get an initial
        # empty renderwindow.
        wx.SafeYield()
        self.render()


    def load_data_from_file(self, file_path):
        """Loads scanvolume data from file. Also sets the volume as input for the sliceviewers
        """
			
		#Process the path
        self._view_frame.SetStatusText("Opening file: %s..." % (file_path))
        filename = os.path.split(file_path)[1]
        fileBaseName =os.path.splitext(filename)[0]

		#Read the vti file
        reader = vtk.vtkXMLImageDataReader()
        reader.SetFileName(file_path)
        reader.GetOutput().SetUpdateExtentToWholeExtent()
        reader.Update()

		#Flip the Y-axis of the image
        flipYFilter = vtk.vtkImageFlip()
        flipYFilter.SetFilteredAxis(1) # Specify which axis will be flipped. 0 for x, 1 for y and 2 for z. 
        flipYFilter.SetInput(reader.GetOutput())
        flipYFilter.Update()

        self.ext = flipYFilter.GetOutput().GetExtent()
        self.spacing = flipYFilter.GetOutput().GetSpacing()
        print(self.spacing)

        self.image_data = self.put_volume_at_origin(flipYFilter.GetOutput())
        self.ext = self.image_data.GetExtent()

        self.slice_viewerA.set_input(self.image_data)
        self.slice_viewerA.ipws[0].SetWindowLevel(3000,900,0) #For T2 slices the window level is (400,100,0). For ADC slices the window level is (4000,2000,0)
        self.slice_viewerA.ipws[0].SetSliceIndex(11)

        self.reset_axial()
        self.slice_viewerA.render()

        self.slice_viewerS.set_input(self.image_data)
        self.slice_viewerS.ipws[0].EnabledOff()
        self.slice_viewerS.ipws[1].EnabledOn()
        self.slice_viewerS.ipws[2].EnabledOff()
        self.slice_viewerS.ipws[1].SetWindowLevel(3000,900,0)
        self.slice_viewerS.ipws[1].SetSliceIndex(126)
        self.reset_sagittal()
        self.slice_viewerS.render()

        self.slice_viewerC.set_input(self.image_data)
        self.slice_viewerC.ipws[0].EnabledOff()
        self.slice_viewerC.ipws[1].EnabledOff()
        self.slice_viewerC.ipws[2].EnabledOn()
        self.slice_viewerC.ipws[2].SetWindowLevel(3000,900,0)
        self.slice_viewerC.ipws[2].SetSliceIndex(126)
        self.reset_coronal()
        self.slice_viewerC.render()

        #self._view_frame.slices_sliderA.SetMax(int(float(self.image_data.GetBounds()[5])/float(self.image_data.GetSpacing()[2])))
        self._view_frame.slices_sliderA.SetMax(int(float(self.image_data.GetExtent()[5])))
        self._view_frame.slices_sliderS.SetMax(int(float(self.image_data.GetBounds()[3])/float(self.image_data.GetSpacing()[1])))
        self._view_frame.slices_sliderC.SetMax(int(float(self.image_data.GetBounds()[1])/float(self.image_data.GetSpacing()[0])))

        self._view_frame.SetStatusText("Opened file")


    def reset_axial(self):
        """ Reset the view for the axial slice viewer """
        slice_viewerA = self.slice_viewerA
        slice_viewerA.set_parallel()
        #self.slice_viewerA.ipws[0].SetWindowLevel(20000,3000,0)
        self.renA.GetActiveCamera().SetPosition(slice_viewerA.ipws[0].GetNormal()[0]*1000+slice_viewerA.ipws[0].GetCenter()[0], slice_viewerA.ipws[0].GetNormal()[1]*1000+slice_viewerA.ipws[0].GetCenter()[1], slice_viewerA.ipws[0].GetNormal()[2]*1000+slice_viewerA.ipws[0].GetCenter()[2])
        self.renA.GetActiveCamera().SetFocalPoint(slice_viewerA.ipws[0].GetCenter())
        self.renA.GetActiveCamera().SetViewUp(0,1,0)
        self.renA.GetActiveCamera().SetParallelScale(100)
        self.renA.GetActiveCamera().Zoom(2.5)		
        self.renA.GetActiveCamera().Modified()
        self.slice_viewerA.render()
        print(self.renA.GetActiveCamera().GetPosition())

    def reset_sagittal(self):
        """ Reset the view for the sagittal slice viewer """
        slice_viewerS = self.slice_viewerS
        slice_viewerS.set_parallel()
        self.renS.GetActiveCamera().SetPosition(slice_viewerS.ipws[1].GetNormal()[0]*500+slice_viewerS.ipws[1].GetCenter()[0], slice_viewerS.ipws[1].GetNormal()[1]*500+slice_viewerS.ipws[1].GetCenter()[1], slice_viewerS.ipws[1].GetNormal()[2]*500+slice_viewerS.ipws[1].GetCenter()[2])
        self.renS.GetActiveCamera().SetFocalPoint(slice_viewerS.ipws[1].GetCenter())
        self.renS.GetActiveCamera().SetViewUp(0,0,1)
        self.renS.GetActiveCamera().SetParallelScale(60)
        self.renS.GetActiveCamera().Modified()
        self.slice_viewerS.render()

    def reset_coronal(self):
        """ Reset the view for the coronal slice viewer """
        slice_viewerC = self.slice_viewerC
        slice_viewerC.set_parallel()
        self.renC.GetActiveCamera().SetPosition(slice_viewerC.ipws[2].GetNormal()[0]*500+slice_viewerC.ipws[2].GetCenter()[0], slice_viewerC.ipws[2].GetNormal()[1]*500+slice_viewerC.ipws[2].GetCenter()[1], slice_viewerC.ipws[2].GetNormal()[2]*500+slice_viewerC.ipws[2].GetCenter()[2])
        self.renC.GetActiveCamera().SetFocalPoint(slice_viewerC.ipws[2].GetCenter())
        self.renC.GetActiveCamera().SetViewUp(0,0,1)
        self.renC.GetActiveCamera().SetParallelScale(60)
        self.renC.GetActiveCamera().Modified()
        self.slice_viewerC.render()
		
    def reset_volume(self):
        self.ren_iso.GetActiveCamera().Zoom(3.5)
        self.ren_iso.GetActiveCamera().Modified()
        self.ren_iso.Render()
        self._view_frame.interactor3d.Render()
		
		
    def reset_doseplan(self):
        """ Reset the view for the coronal slice viewer """
        slice_viewerDP = self.slice_viewerDP
        slice_viewerDP.set_parallel()
        self.slice_viewerDP.ipws[0].SetSliceIndex(11) #hard coded spec
        self.renDP.GetActiveCamera().SetPosition(slice_viewerDP.ipws[0].GetNormal()[0]*1000+slice_viewerDP.ipws[0].GetCenter()[0], slice_viewerDP.ipws[0].GetNormal()[1]*1000+slice_viewerDP.ipws[0].GetCenter()[1], slice_viewerDP.ipws[0].GetNormal()[2]*1000+slice_viewerDP.ipws[0].GetCenter()[2])
        self.renDP.GetActiveCamera().SetFocalPoint(slice_viewerDP.ipws[0].GetCenter())
        self.renDP.GetActiveCamera().SetViewUp(0,1,0)
        self.renDP.GetActiveCamera().SetParallelScale(100)
        self.renDP.GetActiveCamera().Modified()
		
    def load_plan_from_file(self, filelist):
        """Loads dose plans data from files - creates and overlays an average dose plan from these
        """

        self.planlist=[]
		
        for i in range(len(filelist)):
            file_path = filelist[i]
            self._view_frame.SetStatusText( "Opening plans: %s..." % (file_path))
            filename = os.path.split(file_path)[1]
            fileBaseName =os.path.splitext(filename)[0]
			
            reader = vtk.vtkXMLImageDataReader()
            reader.SetFileName(file_path)
            reader.GetOutput().SetUpdateExtentToWholeExtent()
            reader.Update()

            flipYFilter = vtk.vtkImageFlip()
            flipYFilter.SetFilteredAxis(1)
            flipYFilter.SetInput(reader.GetOutput())
            flipYFilter.Update()
			
            allined_data = self.put_volume_at_origin(reader.GetOutput())
			
            self.planlist.append(flipYFilter.GetOutput())
			
        self.nr_doseplans = len(filelist)
		
        self._view_frame.nrdp = self.nr_doseplans
		
        self.create_average_plan()
		
        #self._view_frame.slices_sliderA.SetValue(int(float(self.image_data.GetBounds()[5])/float(self.image_data.GetSpacing()[2])/2))
        self._view_frame.slices_sliderS.SetValue(int(float(self.image_data.GetBounds()[3])/float(self.image_data.GetSpacing()[1])/2))
        self._view_frame.slices_sliderC.SetValue(int(float(self.image_data.GetBounds()[1])/float(self.image_data.GetSpacing()[0])/2))

        #self._handler_slices(None)
	
		
    def create_average_plan(self):

        dummy_img = self.planlist[0]
        dummy_img2 = self.planlist[0]
        dummy_img3 = self.planlist[0]

		#Calculate the mean dose plan
        if len(self.planlist)>1:
            for j in range (0, len(self.planlist)):
                math = vtk.vtkImageMathematics()
                math.SetOperationToAdd()
                math.SetInput1(dummy_img)
                math.SetInput2(self.planlist[j])
                math.Update()
                dummy_img = math.GetOutput()

                math2 = vtk.vtkImageMathematics()
                math2.SetOperationToMin()
                math2.SetInput1(dummy_img2)
                math2.SetInput2(self.planlist[j])
                math2.Update()
                dummy_img2 = math2.GetOutput()

                math3 = vtk.vtkImageMathematics()
                math3.SetOperationToMax()
                math3.SetInput1(dummy_img3)
                math3.SetInput2(self.planlist[j])
                math3.Update()
                dummy_img3 = math3.GetOutput()

        mean_math = vtk.vtkImageMathematics()
        mean_math.SetInput(dummy_img)
        mean_math.SetOperationToMultiplyByK()
        mean_math.SetConstantK(1./len(self.planlist))
        mean_math.Update()
		
        mean_plan = mean_math.GetOutput()

		#Calculate the standard deviation at each voxel
        temp_deviation = self.planlist[0]
        temp2_deviation = self.planlist[0]
		
        if len(self.planlist)>1:
            for j in range(0,len(self.planlist)):
			
                math1 = vtk.vtkImageMathematics()
                math1.SetOperationToSubtract()
                math1.SetInput1(self.planlist[j])
                math1.SetInput2(mean_plan)
                math1.Update()
				
                math2 = vtk.vtkImageMathematics()
                math2.SetOperationToSquare()
                math2.SetInput1(math1.GetOutput())
                math2.Update()
				
                deviation = math2.GetOutput()
			
                math3 = vtk.vtkImageMathematics()
                math3.SetOperationToAdd()
                math3.SetInput1(temp_deviation)
                math3.SetInput2(deviation)
                math3.Update()
				
                temp_deviation = math3.GetOutput()
				
        subtract_initial = vtk.vtkImageMathematics()
        subtract_initial.SetOperationToSubtract()
        subtract_initial.SetInput1(temp_deviation)
        subtract_initial.SetInput2(temp2_deviation)
        subtract_initial.Update()
		
        variance = vtk.vtkImageMathematics()
        variance.SetInput(subtract_initial.GetOutput())
        variance.SetOperationToMultiplyByK()
        variance.SetConstantK(1./len(self.planlist))
        variance.Update()
		
        std = vtk.vtkImageMathematics()
        std.SetOperationToSquareRoot()
        std.SetInput1(variance.GetOutput())
        std.Update()
		
        self.mindata = self.put_volume_at_origin(dummy_img2)
        self.maxdata = self.put_volume_at_origin(dummy_img3)

        math4 = vtk.vtkImageMathematics()
        math4.SetOperationToSubtract()
        math4.SetInput1(self.maxdata)
        math4.SetInput2(self.mindata)
        math4.Update()
        self.diffdata = math4.GetOutput()

        self.planext = mean_math.GetOutput().GetExtent()
        self.plandata = self.put_volume_at_origin2(mean_math.GetOutput())
		
        self.stddata = self.put_volume_at_origin2(std.GetOutput())
		
        self.volumedata = self.put_volume_at_origin3(mean_math.GetOutput())
		
        self.volMapper.SetInput(self.volumedata)
        self.surf.SetInput(self.plandata)
		
        for i in range(len(self.planlist)):
            self.doseplans["p{0}".format(i)] = self.put_volume_at_origin2(self.planlist[i])
			
        self.xmin = self.plandata.GetExtent()[0]
        self.xmax = self.plandata.GetExtent()[1]
        self.ymin = self.plandata.GetExtent()[2]
        self.ymax = self.plandata.GetExtent()[3]
        self.zmin = self.plandata.GetExtent()[4]
        self.zmax = self.plandata.GetExtent()[5]
		
        self.create_lut_for_normal_overlay()
			

    def create_lut_for_normal_overlay(self):

        minval_mean = np.min(numpy_support.vtk_to_numpy(self.plandata.GetPointData().GetScalars())[np.nonzero(numpy_support.vtk_to_numpy(self.plandata.GetPointData().GetScalars()))])
        maxval_mean = np.max(numpy_support.vtk_to_numpy(self.plandata.GetPointData().GetScalars())[np.nonzero(numpy_support.vtk_to_numpy(self.plandata.GetPointData().GetScalars()))])

        minval_std = np.min(numpy_support.vtk_to_numpy(self.stddata.GetPointData().GetScalars())[np.nonzero(numpy_support.vtk_to_numpy(self.stddata.GetPointData().GetScalars()))])
        maxval_std = np.max(numpy_support.vtk_to_numpy(self.stddata.GetPointData().GetScalars())[np.nonzero(numpy_support.vtk_to_numpy(self.stddata.GetPointData().GetScalars()))])
		
		#VIRIDIS Color map
		# First we create a ctf and a otf for the data.
        '''ctf = vtk.vtkColorTransferFunction()
        ctf.SetColorSpaceToRGB()
        ctf.AddRGBPoint(0,0.267, 0.004, 0.329) 
        ctf.AddRGBPoint(0.2,0.257, 0.256, 0.526) 
        ctf.AddRGBPoint(0.4, 0.171, 0.452, 0.558) 
        ctf.AddRGBPoint(0.6,0.121, 0.629, 0.532) 
        ctf.AddRGBPoint(0.8,0.3779, 0.7918, 0.3779) 
        ctf.AddRGBPoint(1, 0.866, 0.889, 0.096)'''
		
		#HEATED-BODY color map
        ctf = vtk.vtkColorTransferFunction()
        ctf.SetColorSpaceToRGB()
        ctf.AddRGBPoint(0,0,0,0) 
        ctf.AddRGBPoint(0.2,0.462, 0, 0) 
        ctf.AddRGBPoint(0.4, 0.902, 0, 0) 
        ctf.AddRGBPoint(0.6, 0.902, 0.443, 0)
        ctf.AddRGBPoint(0.8, 0.902, 0.647, 0)	
        ctf.AddRGBPoint(1, 0.902, 0.902, 0)	
		 
		#Just to make an otf complete opaque
        otf = vtk.vtkPiecewiseFunction()
        otf.AddPoint(0,1)
        otf.AddPoint(1,1)
		
		#------------Create a lut for the mean dose plan----------------
		
        self.lut_mean = vtk.vtkLookupTable()
        lutNum_mean = maxval_mean+1
        self.lut_mean.SetNumberOfTableValues(lutNum_mean)

        for ii in range(0, minval_mean):
            self.lut_mean.SetTableValue(ii, 0, 0, 0, 0)
        for ii in range(minval_mean,maxval_mean+1):
            cc = ctf.GetColor(float(ii-minval_mean)/float(lutNum_mean-minval_mean))
            oo = otf.GetValue(float(ii-minval_mean)/float(lutNum_mean-minval_mean))
            self.lut_mean.SetTableValue(ii, cc[0], cc[1], cc[2], oo)
			
        self.lut_mean.Modified()
        self.lut_mean.Build()
		
		#-------------Create a lut for deviations dose plan-------------------
        self.lut_std = vtk.vtkLookupTable()
        lutNum_std = maxval_std +1
        self.lut_std.SetNumberOfTableValues(lutNum_std)

        for ii in range(0, minval_std):
            self.lut_std.SetTableValue(ii, 0, 0, 0, 0)
        for ii in range(minval_std,maxval_std+1):
            cc = ctf.GetColor(float(ii-minval_std)/float(lutNum_std-minval_std))
            oo = otf.GetValue(float(ii-minval_std)/float(lutNum_std-minval_std))
            self.lut_std.SetTableValue(ii, cc[0], cc[1], cc[2], oo)
			
        self.lut_std.Modified()
        self.lut_std.Build()
		
		
		#Yellow-blue color map
        ctf3d = vtk.vtkColorTransferFunction()
        ctf3d.AddRGBPoint(0, 0, 0, 1) # blue
        ctf3d.AddRGBPoint(0.55, 0, 0, 1) # blue
        ctf3d.AddRGBPoint(0.77, 0.5, 0.5, 0.5) # gray
        ctf3d.AddRGBPoint(1, 1,1,0) #yellow
		
        self.lut_bar = vtk.vtkLookupTable()
        self.lut_bar.SetNumberOfTableValues(lutNum_mean)
		
        for ii in range(0, minval_mean):
            self.lut_bar.SetTableValue(ii, 0, 0, 0, 0)
        for ii in range(minval_mean,maxval_mean+1):
            cc = ctf3d.GetColor(float(ii-minval_mean)/float(lutNum_mean-minval_mean))
            oo = otf.GetValue(float(ii-minval_mean)/float(lutNum_mean-minval_mean))
            self.lut_bar.SetTableValue(ii, cc[0], cc[1], cc[2], oo)
			
        self.lut_bar.Modified()
        self.lut_bar.Build()
		
        lut_50band = vtk.vtkLookupTable()
        lut_50band.SetNumberOfTableValues(3)
        lut_50band.SetTableValue(0,0,0,0,0)
        lut_50band.SetTableValue(1, 0.38,0.35,0.74)
        lut_50band.SetTableValue(2, 0.38,0.35,0.74)
        lut_50band.Modified()
        lut_50band.Build()
		
        lut_100band = vtk.vtkLookupTable()
        lut_100band.SetNumberOfTableValues(3)
        lut_100band.SetTableValue(0,0,0,0,0)
        lut_100band.SetTableValue(1, 0.812,0.792,1)
        lut_100band.SetTableValue(2, 0.812,0.792,1)
        lut_100band.Modified()
        lut_100band.Build()
		
        #Yellow 100%band
        lut100band1 = vtk.vtkLookupTable()
        lut100band1.SetNumberOfTableValues(3)
        lut100band1.SetTableValue(0,0,0,0,0)
        lut100band1.SetTableValue(1, 1, 1, 0, 0.6)
        lut100band1.SetTableValue(2, 1,1,0, 0.6)
        lut100band1.Modified()
        lut100band1.Build()
		
		#Yellow 50%band
        lut50band1 = vtk.vtkLookupTable()
        lut50band1.SetNumberOfTableValues(3)
        lut50band1.SetTableValue(0,0,0,0,0)
        lut50band1.SetTableValue(1, 1, 1, 0, 0.82)
        lut50band1.SetTableValue(2, 1,1,0, 0.82)
        lut50band1.Modified()
        lut50band1.Build()
		
		#Red 100%band
        lut100band2 = vtk.vtkLookupTable()
        lut100band2.SetNumberOfTableValues(3)
        lut100band2.SetTableValue(0,0,0,0,0)
        lut100band2.SetTableValue(1, 0.98,0,0, 0.42)
        lut100band2.SetTableValue(2, 0.98,0,0, 0.42)
        lut100band2.Modified()
        lut100band2.Build()
		
		#Red 50%band
        lut50band2 = vtk.vtkLookupTable()
        lut50band2.SetNumberOfTableValues(3)
        lut50band2.SetTableValue(0,0,0,0,0)
        lut50band2.SetTableValue(1, 0.98,0,0, 0.65)
        lut50band2.SetTableValue(2, 0.98,0,0, 0.65)
        lut50band2.Modified()
        lut50band2.Build()
        
		#Good values: 0.37(red) and 0.5(blue)
        
		#Blue 100%band
        lut100band3 = vtk.vtkLookupTable()
        lut100band3.SetNumberOfTableValues(3)
        lut100band3.SetTableValue(0,0,0,0,0)
        lut100band3.SetTableValue(1,0,0.643,0.941, 0.5)
        lut100band3.SetTableValue(2,0,0.643,0.941, 0.5)
        lut100band3.Modified()
        lut100band3.Build()
		
		#Blue 50%band
        lut50band3 = vtk.vtkLookupTable()
        lut50band3.SetNumberOfTableValues(3)
        lut50band3.SetTableValue(0,0,0,0,0)
        lut50band3.SetTableValue(1,0,0.643,0.941, 0.75)
        lut50band3.SetTableValue(2,0,0.643,0.941, 0.75)
        lut50band3.Modified()
        lut50band3.Build()
		
			
        self.slice_viewerA.overlay_ipws[0].SetLookupTable(self.lut_mean)
        self.slice_viewerS.overlay_ipws[1].SetLookupTable(self.lut_mean)
        self.slice_viewerC.overlay_ipws[2].SetLookupTable(self.lut_mean)
		
        self.slice_viewerA.overlay_ipws_100band1[0].SetLookupTable(lut100band1)
        self.slice_viewerS.overlay_ipws_100band1[1].SetLookupTable(lut100band1)
        self.slice_viewerC.overlay_ipws_100band1[2].SetLookupTable(lut100band1)
		
        self.slice_viewerA.overlay_ipws_50band1[0].SetLookupTable(lut50band1)
        self.slice_viewerS.overlay_ipws_50band1[1].SetLookupTable(lut50band1)
        self.slice_viewerC.overlay_ipws_50band1[2].SetLookupTable(lut50band1)
		
        self.slice_viewerA.overlay_ipws_100band2[0].SetLookupTable(lut100band2)
        self.slice_viewerS.overlay_ipws_100band2[1].SetLookupTable(lut100band2)
        self.slice_viewerC.overlay_ipws_100band2[2].SetLookupTable(lut100band2)
		
        self.slice_viewerA.overlay_ipws_50band2[0].SetLookupTable(lut50band2)
        self.slice_viewerS.overlay_ipws_50band2[1].SetLookupTable(lut50band2)
        self.slice_viewerC.overlay_ipws_50band2[2].SetLookupTable(lut50band2)
		
        self.slice_viewerA.overlay_ipws_100band3[0].SetLookupTable(lut100band3)
        self.slice_viewerS.overlay_ipws_100band3[1].SetLookupTable(lut100band3)
        self.slice_viewerC.overlay_ipws_100band3[2].SetLookupTable(lut100band3)
		
        self.slice_viewerA.overlay_ipws_50band3[0].SetLookupTable(lut50band3)
        self.slice_viewerS.overlay_ipws_50band3[1].SetLookupTable(lut50band3)
        self.slice_viewerC.overlay_ipws_50band3[2].SetLookupTable(lut50band3)

        self.scBar_mean.SetLookupTable(self.lut_mean)
        self.scBar_mean.SetNumberOfLabels(2)
        self.scBar_mean.SetTitle('Radiation (Gy)')
        self.scBar_mean.SetMaximumNumberOfColors(lutNum_mean)
        self.scBar_mean.SetPosition(0.80,0.17)
        #self.scBar.SetWidth(0.05)
        #self.scBar.VisibilityOn()
        #self.scBar.Modified()
        #self.renA.AddActor2D(self.scBar)
		
        self.scBar_std.SetLookupTable(self.lut_std)
        self.scBar_std.SetNumberOfLabels(2)
        self.scBar_std.SetTitle('Standard Deviation ')
        self.scBar_std.SetMaximumNumberOfColors(lutNum_std)
        self.scBar_std.SetPosition(0.80,0.17)
		
		# create the scalar_bar_widget
        self.scBarWidget.SetInteractor(self._view_frame.axial)
        self.scBarWidget.SetScalarBarActor(self.scBar_mean)

        self.slice_viewerA.set_overlay_input(self.plandata)
        self.slice_viewerS.set_overlay_inputS(self.plandata)
        self.slice_viewerC.set_overlay_inputC(self.plandata)
        self.slice_viewerA.render()
        self.slice_viewerS.render()
        self.slice_viewerC.render()
        self._view_frame.SetStatusText("Opened plan file from patient " + self.item)
		
    def put_volume_at_origin(self,data):
        """ This is needed to 'allineate' all datasets
        """

        spacing = self.spacing
        self.newspacing = spacing
        lower_left_extent = (data.GetExtent()[0],data.GetExtent()[2],data.GetExtent()[4])
        world= map(operator.mul, spacing, lower_left_extent)
        world= map(operator.mul, world, (-1, -1,-1))

        translate_extent = vtk.vtkImageTranslateExtent()
        translate_extent.SetInput(data)
        translate_extent.SetTranslation(map(operator.mul, lower_left_extent, (-1, -1,-1)))
        translate_extent.Update()

        changeinfo = vtk.vtkImageChangeInformation()
        changeinfo.SetOutputOrigin(0,0,0)
        changeinfo.SetInput(translate_extent.GetOutput())
        changeinfo.SetOutputSpacing((self.newspacing))
        changeinfo.Update()

        shift_scale = vtk.vtkImageShiftScale()
        shift_scale.SetInput(changeinfo.GetOutput())
        shift_scale.SetOutputScalarTypeToInt()
        shift_scale.Update()
		
        flipYFilter = vtk.vtkImageFlip()
        flipYFilter.SetFilteredAxis(1)
        flipYFilter.SetInput(shift_scale.GetOutput())
        flipYFilter.Update()
		
        #return flipYFilter.GetOutput()
		
        return shift_scale.GetOutput()
		
    def put_volume_at_origin2(self,data):
        """ This is needed to 'allineate' all datasets
        """

        spacing = self.spacing
        self.newspacing = spacing
        lower_left_extent = (data.GetExtent()[0],data.GetExtent()[2],data.GetExtent()[4])
        world= map(operator.mul, spacing, lower_left_extent)
        world= map(operator.mul, world, (-1, -1,-1))

        translate_extent = vtk.vtkImageTranslateExtent()
        translate_extent.SetInput(data)
        translate_extent.SetTranslation(map(operator.mul, lower_left_extent, (-1, -1,-1)))
        translate_extent.Update()

        changeinfo = vtk.vtkImageChangeInformation()
        changeinfo.SetOutputOrigin(0,0,0)
        changeinfo.SetInput(translate_extent.GetOutput())
        changeinfo.SetOutputSpacing((self.newspacing))
        changeinfo.Update()

        shift_scale = vtk.vtkImageShiftScale()
        shift_scale.SetInput(changeinfo.GetOutput())
        shift_scale.SetOutputScalarTypeToInt()
        shift_scale.Update()
		
        flipYFilter = vtk.vtkImageFlip()
        flipYFilter.SetFilteredAxis(1)
        flipYFilter.SetInput(shift_scale.GetOutput())
        flipYFilter.Update()
		
        return flipYFilter.GetOutput()
		
        #return shift_scale.GetOutput()

		
    def put_volume_at_origin3(self,data):
        """ This is needed to 'allineate' all datasets
        """

        spacing = self.spacing
        self.newspacing = spacing
        lower_left_extent = (data.GetExtent()[0],data.GetExtent()[2],data.GetExtent()[4])
        world= map(operator.mul, spacing, lower_left_extent)
        world= map(operator.mul, world, (-1, -1,-1))

        translate_extent = vtk.vtkImageTranslateExtent()
        translate_extent.SetInput(data)
        translate_extent.SetTranslation(map(operator.mul, lower_left_extent, (-1, -1,-1)))
        translate_extent.Update()

        changeinfo = vtk.vtkImageChangeInformation()
        changeinfo.SetOutputOrigin(0,0,0)
        changeinfo.SetInput(translate_extent.GetOutput())
        changeinfo.SetOutputSpacing((self.newspacing))
        changeinfo.Update()

        shift_scale = vtk.vtkImageShiftScale()
        shift_scale.SetInput(changeinfo.GetOutput())
        shift_scale.SetOutputScalarTypeToUnsignedChar() #this is needed for the volume rendering
        shift_scale.Update()
		
        flipYFilter = vtk.vtkImageFlip()
        flipYFilter.SetFilteredAxis(1)
        flipYFilter.SetInput(shift_scale.GetOutput())
        flipYFilter.Update()
		
        return flipYFilter.GetOutput()
		
		
    def _handler_slices(self, event, control_id):
        """ Handler to coordinate the slices """
		
		#1 for axial slider
		#2 for axial spin
		#3 for axial scroll
		
        vf = self._view_frame
		
        if control_id == "sliderA":
            self.slice_viewerA.ipws[0].SetSliceIndex(vf.slices_sliderA.GetValue())
            vf.slices_spinA.SetValue(vf.slices_sliderA.GetValue())
            self.slice_viewerA.render()
			
        if control_id == "spinA":
            self.slice_viewerA.ipws[0].SetSliceIndex(vf.slices_spinA.GetValue())
            vf.slices_sliderA.SetValue(vf.slices_spinA.GetValue())
            self.slice_viewerA.render()
			
        if control_id == "sliderS":
            self.slice_viewerS.ipws[1].SetSliceIndex(vf.slices_sliderS.GetValue())
            vf.slices_spinS.SetValue(vf.slices_sliderS.GetValue())
            self.slice_viewerS.render()
			
        if control_id == "spinS":
            self.slice_viewerS.ipws[1].SetSliceIndex(vf.slices_spinS.GetValue())
            vf.slices_sliderS.SetValue(vf.slices_spinS.GetValue())
            self.slice_viewerS.render()	
			
        if control_id == "sliderC":
            self.slice_viewerC.ipws[2].SetSliceIndex(vf.slices_sliderC.GetValue())
            vf.slices_spinC.SetValue(vf.slices_sliderC.GetValue())
            self.slice_viewerC.render()
			
        if control_id == "spinC":
            self.slice_viewerC.ipws[2].SetSliceIndex(vf.slices_spinC.GetValue())
            vf.slices_sliderC.SetValue(vf.slices_spinC.GetValue())
            self.slice_viewerC.render()
			
        idx_axial = self.slice_viewerA.ipws[0].GetSliceIndex()
        idx_sagittal = self.slice_viewerS.ipws[1].GetSliceIndex()
        idx_coronal = self.slice_viewerC.ipws[2].GetSliceIndex()
		
        self.analyse_checkboxes_isovalue(idx_axial,idx_sagittal,idx_coronal)
		
        self.slice_viewerA.render()
        self.slice_viewerS.render()
        self.slice_viewerC.render()

    def _bind_events(self):
        """Bind wx events to Python callable object event handlers.
        """

        vf = self._view_frame
		
		#Bind the events
        #vf.Bind(wx.EVT_MENU, self._handler_file_open, id = vf.id_file_open)
		
        vf.Bind(wx.EVT_MENU, self._handler_default_view, id=vf.views_default_id)
        vf.Bind(wx.EVT_MENU, self._handler_max_image_view, id=vf.views_max_image_id)
        vf.Bind(wx.EVT_MENU, self._handler_contour_view, id=vf.views_contour_view_id)
        vf.Bind(wx.EVT_MENU, self._handler_voxel_view, id=vf.views_voxel_view_id)
		
        vf.toolbar.Bind(wx.EVT_TOOL, self.OnOpen, vf.load_patient) #Open patient data
        vf.toolbar.Bind(wx.EVT_TOOL, self.OnSave, vf.save) # Save current state
		
        vf.patient_list.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightClickPatient) #pop-up menu on right click
        vf.patient_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelect)

        vf.slices_sliderA.Bind(wx.EVT_SLIDER, lambda evt: self._handler_slices(evt, "sliderA"))
        vf.slices_spinA.Bind(wx.EVT_SPINCTRL, lambda evt: self._handler_slices(evt, "spinA"))
		
        vf.slices_sliderS.Bind(wx.EVT_SLIDER, lambda evt: self._handler_slices(evt, "sliderS"))
        vf.slices_spinS.Bind(wx.EVT_SPINCTRL, lambda evt: self._handler_slices(evt, "spinS"))
		
        vf.slices_sliderC.Bind(wx.EVT_SLIDER, lambda evt: self._handler_slices(evt, "sliderC"))
        vf.slices_spinC.Bind(wx.EVT_SPINCTRL, lambda evt: self._handler_slices(evt, "spinC"))
		
        vf.canvash.mpl_connect('button_press_event', self.onPicksquare)
		
		
        vf.generate_button.Bind(wx.EVT_BUTTON, self._render_3dplan)
        vf.slider_dose3d.Bind(wx.EVT_SLIDER, lambda evt: self._change_dose3d(evt, 1))
        vf.spin_dose3d.Bind(wx.EVT_SPINCTRL, lambda evt: self._change_dose3d(evt, 2))
		
        vf.show_overlay.Bind(wx.EVT_CHECKBOX, self._show_overlay)
		
        vf.select1.Bind(wx.EVT_RADIOBUTTON, self.OnRadioSelect)
        vf.select2.Bind(wx.EVT_RADIOBUTTON, self.OnRadioSelect)
		
        vf.radio_mean.Bind(wx.EVT_RADIOBUTTON, self.OnRadioColorMap)
        vf.radio_std.Bind(wx.EVT_RADIOBUTTON, self.OnRadioColorMap)
		
        vf.slices_resetA.Bind(wx.EVT_BUTTON, self._handler_reset_all)
        vf.slices_resetC.Bind(wx.EVT_BUTTON, self._handler_reset_all)
        vf.slices_resetS.Bind(wx.EVT_BUTTON, self._handler_reset_all)

		#CONTROL check
		
        self.toggled = False
		
        self.balloon_axial.AddObserver('TimerEvent', self.balloonCallback)
        self.balloon_axial.AddObserver('EndInteractionEvent', self.balloonCallback)
		
        self.balloon_sagittal.AddObserver('TimerEvent', self.balloonCallback)
        self.balloon_sagittal.AddObserver('EndInteractionEvent', self.balloonCallback)
		
        self.balloon_coronal.AddObserver('TimerEvent', self.balloonCallback)
        self.balloon_coronal.AddObserver('EndInteractionEvent', self.balloonCallback)
		
        #vf.axial.Bind(wx.EVT_LEFT_UP, self.onLeftUp)
        #vf.axial.Bind(wx.EVT_LEFT_DOWN, self.onLeftDown)
        vf.axial.Bind(wx.EVT_MOTION, self.onMotion)
		
		
        self.slice_viewerA.ipws[0].AddObserver('StartInteractionEvent', lambda e, o: self._ipwStartInteractionCallback(1))
        self.slice_viewerA.ipws[0].AddObserver('InteractionEvent', lambda e, o: self._ipwInteractionCallback(1))
        self.slice_viewerA.ipws[0].AddObserver('EndInteractionEvent', lambda e, o: self._ipwEndInteractionCallback(1, e))
        #self.slice_viewerA.ipws[0].AddObserver('EndInteractionEvent', self._ipwEndInteractionCallback)
		
        #self.slice_viewerA.picker.AddObserver('PickEvent',self._pick_event)
		
			
    def _render_3dplan(self,event):
        
        self.ren_iso.RemoveAllViewProps()
	
        self.otf_3d.RemoveAllPoints()
        self.otf_3d.AddPoint(0, 0)
        self.otf_3d.AddPoint(100, 1)
	
        self.volMapper.SetInput(self.volumedata)
	
        #self.ren_iso.AddVolume(self.vol)
        self.ren_iso.AddActor(self.silh_actor)
        self.ren_iso.AddActor(self.surf_actor)
		
        self.ren_iso.ResetCamera()
        self.ren_iso.GetActiveCamera().Zoom(3.5)
        self._view_frame.interactor3d.Render()
	
		
    def _change_dose3d(self,event, control_id):
        vf = self._view_frame
        self.ren_iso.RemoveVolume(self.vol)
		
        if control_id == 1:
            vf.spin_dose3d.SetValue(vf.slider_dose3d.GetValue())
            dose = vf.spin_dose3d.GetValue()
        elif control_id == 2:
            vf.slider_dose3d.SetValue(vf.spin_dose3d.GetValue())
            dose = vf.slider_dose3d.GetValue()
		
        self.otf_3d.RemoveAllPoints()
        self.otf_3d.AddPoint(0, 0)
        self.otf_3d.AddPoint(dose-1, 0)
        self.otf_3d.AddPoint(dose, 1)
        self.otf_3d.AddPoint(dose+1, 0)
        self.otf_3d.AddPoint(100, 0)
		
        self.ren_iso.AddVolume(self.vol)
        self.ren_iso.AddActor(self.silh_actor)
        self._view_frame.interactor3d.Render()
		

    def extractVoxels(self, evt,obj):
        vf = self._view_frame
		
        self._view_frame.ax_violin.cla()
        self._view_frame.ax_violin.set_xlabel("Voxel values")
        self._view_frame.ax_violin.set_ylabel("Density")
		
        path = vtk.vtkPolyData()
        vf.tracer.GetPath(path)
		
        slice_index = self.slice_viewerA.ipws[0].GetSliceIndex()
		
        voxel_arrays = []
		
        for i in range(len(self.planlist)):
            extractSlice = vtk.vtkExtractVOI()
            extractSlice.SetInput(self.doseplans["p{0}".format(i)])
            extractSlice.SetVOI(self.xmin, self.xmax, self.ymin, self.ymax, slice_index, slice_index)
            extractSlice.SetSampleRate(1, 1, 1)
            extractSlice.Update()
		
            # creating input source for polydata -> stencil
            p2s = vtk.vtkPolyDataToImageStencil()
            p2s.SetInput(path)
            p2s.SetOutputSpacing(self.plandata.GetSpacing())
            p2s.SetOutputOrigin(self.plandata.GetOrigin())
            p2s.Update()
	
            #Convert image stencil to vtkImageData
            stencil = vtk.vtkImageStencil()
            stencil.SetStencil(p2s.GetOutput())
            stencil.SetInput(extractSlice.GetOutput())   #input is vtkImageData
            stencil.ReverseStencilOff()
            stencil.SetBackgroundColor(1,1,0,1)
            stencil.SetBackgroundValue(0)
            stencil.Update()
		
            scalars = stencil.GetOutput().GetPointData().GetScalars()
            voxels = numpy_support.vtk_to_numpy(scalars)[np.nonzero(numpy_support.vtk_to_numpy(scalars))]
			
            voxel_arrays.append(voxels)
			
            #print("Doseplan %s" %(i))
            #print(voxels)
			
		
        data = list(chain.from_iterable(zip(*voxel_arrays)))
		
        data_per_voxel = [data[x:x+len(self.planlist)] for x in range(0, len(data), len(self.planlist))]
		
        for voxel_array in data_per_voxel:
            voxel_array_np = np.array(voxel_array)
            sns.distplot(voxel_array_np, rug=True, hist=False, color="r", ax=self._view_frame.ax_violin)
        
        self._view_frame.canvas_violin.draw()
		
		
		
    def OnRadioSelect(self,event):
	
        vf = self._view_frame
		
        if str(vf.select1.GetValue()) == "True":
			#Activate voxel selection
            vf.tracer.Off()
        else:
            #print("Region enabled")
			#Activate region selection
            picker = vtk.vtkCellPicker()
            self.slice_viewerA.overlay_ipws[0].SetPicker(picker)
            #self.slice_viewerA.ipws[0].SetPicker(picker)
            pc = picker.GetPickList()
            vf.tracer.SetInteractor(self._view_frame.axial) 
            vf.tracer.SetViewProp(pc.GetLastProp())
            vf.tracer.AddObserver('EndInteractionEvent',self.extractVoxels)
            vf.tracer.On()
            vtk.vtkMapper.SetResolveCoincidentTopologyToPolygonOffset()  
            vtk.vtkMapper.SetResolveCoincidentTopologyPolygonOffsetParameters(10,10)
			

    def OnRadioColorMap(self,event):
        vf = self._view_frame
		
        if vf.show_overlay.IsChecked():
		
            if str(vf.radio_mean.GetValue()) == "True":
				#Activate color map for mean
                self.slice_viewerA.overlay_ipws[0].SetLookupTable(self.lut_mean)
                self.slice_viewerS.overlay_ipws[1].SetLookupTable(self.lut_mean)
                self.slice_viewerC.overlay_ipws[2].SetLookupTable(self.lut_mean)
                self.slice_viewerA.set_overlay_input(self.plandata)
                self.slice_viewerC.set_overlay_inputC(self.plandata)
                self.slice_viewerS.set_overlay_inputS(self.plandata)
				
				#Colorbar
                self.scBarWidget.SetScalarBarActor(self.scBar_mean)
                #self.scBarWidget.On()
				
				
            else:
                self.slice_viewerA.overlay_ipws[0].SetLookupTable(self.lut_std)
                self.slice_viewerS.overlay_ipws[1].SetLookupTable(self.lut_std)
                self.slice_viewerC.overlay_ipws[2].SetLookupTable(self.lut_std)
                self.slice_viewerA.set_overlay_input(self.stddata)
                self.slice_viewerC.set_overlay_inputC(self.stddata)
                self.slice_viewerS.set_overlay_inputS(self.stddata)
				
				#Colorbar
                self.scBarWidget.SetScalarBarActor(self.scBar_std)
                #self.scBarWidget.On()

            self.scBarWidget.On()
            self.slice_viewerA.render()
            self.slice_viewerS.render()
            self.slice_viewerC.render()
			
			
    def OnCheckBox(self,event):
        id = event.GetEventObject().GetId()
		
        color = self._view_frame.isovalue_list.GetItem(id).GetBackgroundColour()
			
        color_list = list(color)
			
        float_color = [round(c/255,3) for c in color_list]
			
        isovalue = self.isoline_sliders[id].GetValue()
        print(isovalue)
        index = self.dic_iso_to_index[isovalue]
        print(index)

        if self.actives[id].IsChecked():
            self.bars[index].set_facecolor(float_color)
            self._view_frame.canvasb.draw()
        else:
            self.bars[index].set_facecolor(self.default_barcolor)
            self._view_frame.canvasb.draw()
				
        event.Skip()
	
    def _ipwStartInteractionCallback(self, viewer_id):
        """Method for handling seedpoint selection in the ipw
        """
        self.tempCursorData = None
        self._ipwInteractionCallback(viewer_id)

    def _ipwInteractionCallback(self, viewer_id):
        """Method for handling seedpoint selection in the ipw
        """ 
        cd = 4 * [0.0]
        if viewer_id == 1 and self.slice_viewerA.ipws[0].GetCursorData(cd):
            self.tempCursorData = cd
        elif viewer_id == 2 and self.slice_viewerS.ipws[1].GetCursorData(cd):
            self.tempCursorData = cd
        elif viewer_id == 3 and self.slice_viewerC.ipws[2].GetCursorData(cd):
            self.tempCursorData = cd

    def onLeftDown(self,evt):
		self.CaptureMouse()
		evt.Skip()
			
    def onLeftUp(self, evt):
        """Method for handling seedpoint selection in the ipw
        """
        self.distPlot(self.tempCursorData)
        evt.Skip()
		
    def onMotion(self,evt):
		self.shiftIsCurrentlyDown = evt.ShiftDown()
		if (evt.Dragging() and evt.LeftIsDown()) or evt.LeftIsDown():
			self.distPlot(self.tempCursorData)
		evt.Skip()
		
    def _ipwEndInteractionCallback(self, viewer_id, event):
        """Method for handling seedpoint selection in the ipw
        """
        self.distPlot(self.tempCursorData)
        
	
    def clearSeedPoints(self):
        """Method for clearing the seedpoint list
        """
        self.seedPoints = []        
        self._view_frame.seedpoint_list.DeleteAllItems()
	
    def _reset_barchart(self,event):
        
        vf = self._view_frame
		
        vf.chart.GetAxis(vtk.vtkAxis.LEFT).SetRange(0,1)
        vf.chart.GetAxis(vtk.vtkAxis.BOTTOM).SetRange(65,95)
		
        self.ren_plot.GetRenderer().Render()
        vf.plot_uncertainty.Render()
		
		
    def balloonCallback(self,obj,event):

		#First, we get the contour that we are hovering. 
        contour = obj.GetCurrentProp()
		
        if contour is not None:
            color = contour.GetProperty().GetColor()
            #print(color)
		
			#We get the string associated with that contour, something like dose260-{x}
            dose = obj.GetBalloonString(contour) 
		
			#We filter the string to just get the id. Ex: "dose260-8" ---> re expression ---> 8
            doseid = int(re.findall('\d+|\D+', dose)[3])
			#We get the current isovalue
            isovalue = int(re.findall('\d+|\D+', dose)[5])
			
            #print(doseid)
            #print(isovalue)
		
			#Small math to compensate for the heatmap. 
			
            doseidfinal = self.nr_doseplans - (doseid + 1) 
		
            self.rectangle = mpatches.Rectangle((isovalue-70, doseidfinal),1,1,fill=False, edgecolor="#FF00FF",linewidth=2.5)
			#change color to color of active contour
		
            self._view_frame.axh.add_patch(self.rectangle)
			
            self._view_frame.canvash.draw()   
            self.rectangle.remove()
		
	
    def OnRightClickPatient(self, event):
        # only do this part the first time so the events are only bound once
        if not hasattr(self, "popupID1"):
            self.popupID1 = wx.NewId()
            self.popupID2 = wx.NewId()
            self.popupID3 = wx.NewId()
            self.popupID4 = wx.NewId()
            
        # make a menu
        menu = wx.Menu()
        # add some items
        menu.Append(self.popupID1, "Delete Patient")
        menu.Append(self.popupID2, "Load data into slice viewer")
        menu.Append(self.popupID3, "Change volume data")
        menu.Append(self.popupID4, "Change dose plans")

        # Popup the menu.  If an item is selected then its handler
        # will be called before PopupMenu returns.
        self._view_frame.PopupMenu(menu)
		
        self._view_frame.Bind(wx.EVT_MENU, self.delete_patient,id=self.popupID1)
        self._view_frame.Bind(wx.EVT_MENU, self.load_volume_and_plans,id=self.popupID2)
		
        menu.Destroy()
		
    def OnRightClickIsovalue(self, event):
        # only do this part the first time so the events are only bound once
        if not hasattr(self, "popupIDiso"):
            self.popupIDiso = wx.NewId()
            
        # make a menu
        menu = wx.Menu()
        # add some items
        menu.Append(self.popupIDiso, "Remove this isovalue")

        # Popup the menu.  If an item is selected then its handler
        # will be called before PopupMenu returns.
        self._view_frame.PopupMenu(menu)
		
        self._view_frame.Bind(wx.EVT_MENU, self.delete_isovalue,id=self.popupIDiso)
		
        menu.Destroy()
	
    def OnSelect(self,event):
        self.index = event.GetIndex()
        self.item = event.GetItem().GetText()
        #print(self.index)
        #print(self.item)
	
    def delete_patient(self,event):
        self._view_frame.patient_list.DeleteItem(self.index)
        del self._view_frame.patients[int(self.item)]
		
    def delete_isovalue(self,event):
        self._view_frame.isovalue_list.DeleteItem(self.index)
        #del self._view_frame.isovalue_list[int(self.item)]
	
    def load_volume_and_plans(self,event):
        #start = time.time()
        patientinfo = self._view_frame.patients.get(int(self.item))
		
        self.load_data_from_file(patientinfo[0])
        self.load_plan_from_file(patientinfo[1])
		
        #print(patientinfo[0])
        name_file = os.path.split(patientinfo[0])[1]
        #print(name_file)
		
        if name_file == "pb_ano1.vti":
		    self.create_mean_std_file(name_file)
		    self.scatterPlot()
        else: 
            self._initialize_boxplot()
			
            self.checked = []
            self._view_frame.isovalue_list.Bind(ulc.EVT_LIST_ITEM_CHECKED, self.OnVisible)
            self._view_frame.isovalue_list.Bind(wx.EVT_RADIOBUTTON, self.OnRadioButton)
            self._view_frame.isovalue_list.Bind(wx.EVT_SLIDER, lambda evt: self._change_isovalue_multiple(evt, 1))
            self._view_frame.isovalue_list.Bind(wx.EVT_SPINCTRL, lambda evt: self._change_isovalue_multiple(evt, 2))
			#self._view_frame.isovalue_list.Bind(csel.EVT_COLOURSELECT, self.OnChooseBackground)
            self._view_frame.isovalue_list.Bind(wx.EVT_COMBOBOX, self.OnComboBox)
            self._view_frame.isovalue_list.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightClickIsovalue)
            #self._view_frame.isovalue_list.Bind(wx.EVT_COLOURPICKER_CHANGED, self.OnChooseBackground)
            self._view_frame.isovalue_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelect)
		
            self.BarPlotwithData()
            self.heatMap()
			#start = time.time()
            self.create_mean_std_file(name_file)
            self.scatterPlot()
			#end = time.time()
			
        self._view_frame.SetStatusText( "Done.")
		
    def OnVisible(self,event):
	
        vf = self._view_frame
	
        id = event.GetIndex()
		
        option = self.options[id].GetValue()
		
        idx_axial = self.slice_viewerA.ipws[0].GetSliceIndex()
        idx_sagittal = self.slice_viewerS.ipws[1].GetSliceIndex()
        idx_coronal = self.slice_viewerC.ipws[2].GetSliceIndex()
		
        isovalue = self.isoline_sliders[id].GetValue()
        median = self.median_outliers_ids["i{0}".format(isovalue)][0]
        outliers = self.median_outliers_ids["i{0}".format(isovalue)][1]
		
        if vf.isovalue_list.GetItem(id,0).IsChecked():
            self.balloon_axial.EnabledOn()
            self.balloon_sagittal.EnabledOn()
            self.balloon_coronal.EnabledOn()
		
            if option == "Contours":
                for plan in range(len(self.planlist)):
                    self.renA.AddActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                    self.renS.AddActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                    self.renC.AddActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
                    self.balloon_axial.AddBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)] ,'dose260-' + str(plan) + "\n" + "Isovalue" + str(isovalue))
                    self.balloon_sagittal.AddBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)] ,'dose260-' + str(plan) + "\n" + "Isovalue" + str(isovalue))
                    self.balloon_coronal.AddBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)] ,'dose260-' + str(plan) + "\n" + "Isovalue" + str(isovalue))
					
            elif option == "Median":
                for plan in range(len(self.planlist)):
                    self.balloon_axial.RemoveBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                    self.balloon_sagittal.RemoveBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                    self.balloon_coronal.RemoveBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
                    self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                    self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                    self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
					
                self.renA.AddActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)])	
                self.renS.AddActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)])
                self.renC.AddActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)])
                self.balloon_axial.AddBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))
                self.balloon_sagittal.AddBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))
                self.balloon_coronal.AddBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))				
				
            elif option == "Outliers":
                for plan in range(len(self.planlist)):
                    self.balloon_axial.RemoveBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                    self.balloon_sagittal.RemoveBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                    self.balloon_coronal.RemoveBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
                    self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                    self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                    self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
                for outlier in outliers:
                    #color_outlier = self.ctf_yellow.GetColor(self.contours_info[isovalue][outlier][1])	
                    #self.isovalue_objs[id].set_outlier_contours_to_dark(outlier, color_outlier)
                    self.renA.AddActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(outlier)])
                    self.renS.AddActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(outlier)])
                    self.renC.AddActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(outlier)])
                    self.balloon_axial.AddBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)] ,'dose260-' + str(outlier) + "\n" + "Isovalue" + str(isovalue))
                    self.balloon_sagittal.AddBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)] ,'dose260-' + str(outlier) + "\n" + "Isovalue" + str(isovalue))
                    self.balloon_coronal.AddBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)] ,'dose260-' + str(outlier) + "\n" + "Isovalue" + str(isovalue))					
		
            elif option == "Bands":
                for plan in range(len(self.planlist)):
                    self.balloon_axial.RemoveBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                    self.balloon_sagittal.RemoveBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                    self.balloon_coronal.RemoveBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
                    self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                    self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                    self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])	
                if id == 0:
                    if vf.isovalue_list.GetItem(1,0).IsChecked() and not vf.isovalue_list.GetItem(2,0).IsChecked():
						#Remove red
                        self.slice_viewerA.set_overlay_input_axial_100band2(None)
                        self.slice_viewerS.set_overlay_input_sagittal_100band2(None)
                        self.slice_viewerC.set_overlay_input_coronal_100band2(None)
					
						#Add yellow
                        self.slice_viewerA.set_overlay_input_axial_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                        self.slice_viewerS.set_overlay_input_sagittal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                        self.slice_viewerC.set_overlay_input_coronal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
						
						#Add red
                        self.slice_viewerA.set_overlay_input_axial_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerS.set_overlay_input_sagittal_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerC.set_overlay_input_coronal_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
						
                    elif vf.isovalue_list.GetItem(2,0).IsChecked() and not vf.isovalue_list.GetItem(1,0).IsChecked():	
						#Remove blue
                        self.slice_viewerA.set_overlay_input_axial_100band3(None)
                        self.slice_viewerS.set_overlay_input_sagittal_100band3(None)
                        self.slice_viewerC.set_overlay_input_coronal_100band3(None)
					
						#Add yellow
                        self.slice_viewerA.set_overlay_input_axial_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                        self.slice_viewerS.set_overlay_input_sagittal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                        self.slice_viewerC.set_overlay_input_coronal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
						
						#Add blue
                        self.slice_viewerA.set_overlay_input_axial_100band3(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[2].GetValue())])
                        self.slice_viewerS.set_overlay_input_sagittal_100band3(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[2].GetValue())])
                        self.slice_viewerC.set_overlay_input_coronal_100band3(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[2].GetValue())])
						
                    elif vf.isovalue_list.GetItem(1,0).IsChecked() and vf.isovalue_list.GetItem(2,0).IsChecked():
					
						#Remove red
                        self.slice_viewerA.set_overlay_input_axial_100band2(None)
                        self.slice_viewerS.set_overlay_input_sagittal_100band2(None)
                        self.slice_viewerC.set_overlay_input_coronal_100band2(None)
					
						#Remove blue
                        self.slice_viewerA.set_overlay_input_axial_100band3(None)
                        self.slice_viewerS.set_overlay_input_sagittal_100band3(None)
                        self.slice_viewerC.set_overlay_input_coronal_100band3(None)
					
						#Add yellow
                        self.slice_viewerA.set_overlay_input_axial_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                        self.slice_viewerS.set_overlay_input_sagittal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                        self.slice_viewerC.set_overlay_input_coronal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
						
						#Add blue
                        self.slice_viewerA.set_overlay_input_axial_100band3(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[2].GetValue())])
                        self.slice_viewerS.set_overlay_input_sagittal_100band3(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[2].GetValue())])
                        self.slice_viewerC.set_overlay_input_coronal_100band3(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[2].GetValue())])
						
						#Add red
                        self.slice_viewerA.set_overlay_input_axial_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerS.set_overlay_input_sagittal_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerC.set_overlay_input_coronal_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
					
						
                    self.slice_viewerA.set_overlay_input_axial_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerS.set_overlay_input_sagittal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerC.set_overlay_input_coronal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerA.render()
                    self.slice_viewerS.render()
                    self.slice_viewerC.render()
						
						
                elif id == 1:
                    self.slice_viewerA.set_overlay_input_axial_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerS.set_overlay_input_sagittal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerC.set_overlay_input_coronal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerA.render()
                    self.slice_viewerS.render()
                    self.slice_viewerC.render()
					
                elif id == 2:
                    if vf.isovalue_list.GetItem(1,0).IsChecked():
						#Remove red
                        self.slice_viewerA.set_overlay_input_axial_100band2(None)
                        self.slice_viewerS.set_overlay_input_sagittal_100band2(None)
                        self.slice_viewerC.set_overlay_input_coronal_100band2(None)
					
						#Add blue
                        self.slice_viewerA.set_overlay_input_axial_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                        self.slice_viewerS.set_overlay_input_sagittal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                        self.slice_viewerC.set_overlay_input_coronal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
						
						#Add red
                        self.slice_viewerA.set_overlay_input_axial_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerS.set_overlay_input_sagittal_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerC.set_overlay_input_coronal_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
				
                    self.slice_viewerA.set_overlay_input_axial_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerS.set_overlay_input_sagittal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerC.set_overlay_input_coronal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerA.render()
                    self.slice_viewerS.render()
                    self.slice_viewerC.render()
		
		
            elif option == "100% band":
                for plan in range(len(self.planlist)):
                    self.balloon_axial.RemoveBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                    self.balloon_sagittal.RemoveBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                    self.balloon_coronal.RemoveBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
                    self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                    self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                    self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])	
                if id == 0:
                    if vf.isovalue_list.GetItem(1,0).IsChecked() and not vf.isovalue_list.GetItem(2,0).IsChecked():
						#Remove red
                        self.slice_viewerA.set_overlay_input_axial_100band2(None)
                        self.slice_viewerS.set_overlay_input_sagittal_100band2(None)
                        self.slice_viewerC.set_overlay_input_coronal_100band2(None)
					
						#Add yellow
                        self.slice_viewerA.set_overlay_input_axial_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                        self.slice_viewerS.set_overlay_input_sagittal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                        self.slice_viewerC.set_overlay_input_coronal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
						
						#Add red
                        self.slice_viewerA.set_overlay_input_axial_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerS.set_overlay_input_sagittal_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerC.set_overlay_input_coronal_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
						
                    elif vf.isovalue_list.GetItem(2,0).IsChecked() and not vf.isovalue_list.GetItem(1,0).IsChecked():	
						#Remove blue
                        self.slice_viewerA.set_overlay_input_axial_100band3(None)
                        self.slice_viewerS.set_overlay_input_sagittal_100band3(None)
                        self.slice_viewerC.set_overlay_input_coronal_100band3(None)
					
						#Add yellow
                        self.slice_viewerA.set_overlay_input_axial_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                        self.slice_viewerS.set_overlay_input_sagittal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                        self.slice_viewerC.set_overlay_input_coronal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
						
						#Add blue
                        self.slice_viewerA.set_overlay_input_axial_100band3(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[2].GetValue())])
                        self.slice_viewerS.set_overlay_input_sagittal_100band3(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[2].GetValue())])
                        self.slice_viewerC.set_overlay_input_coronal_100band3(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[2].GetValue())])
						
                    elif vf.isovalue_list.GetItem(1,0).IsChecked() and vf.isovalue_list.GetItem(2,0).IsChecked():
					
						#Remove red
                        self.slice_viewerA.set_overlay_input_axial_100band2(None)
                        self.slice_viewerS.set_overlay_input_sagittal_100band2(None)
                        self.slice_viewerC.set_overlay_input_coronal_100band2(None)
					
						#Remove blue
                        self.slice_viewerA.set_overlay_input_axial_100band3(None)
                        self.slice_viewerS.set_overlay_input_sagittal_100band3(None)
                        self.slice_viewerC.set_overlay_input_coronal_100band3(None)
					
						#Add yellow
                        self.slice_viewerA.set_overlay_input_axial_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                        self.slice_viewerS.set_overlay_input_sagittal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                        self.slice_viewerC.set_overlay_input_coronal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
						
						#Add blue
                        self.slice_viewerA.set_overlay_input_axial_100band3(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[2].GetValue())])
                        self.slice_viewerS.set_overlay_input_sagittal_100band3(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[2].GetValue())])
                        self.slice_viewerC.set_overlay_input_coronal_100band3(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[2].GetValue())])
						
						#Add red
                        self.slice_viewerA.set_overlay_input_axial_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerS.set_overlay_input_sagittal_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerC.set_overlay_input_coronal_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
					
						
                    self.slice_viewerA.set_overlay_input_axial_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerS.set_overlay_input_sagittal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerC.set_overlay_input_coronal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerA.render()
                    self.slice_viewerS.render()
                    self.slice_viewerC.render()
						
						
                elif id == 1:
                    self.slice_viewerA.set_overlay_input_axial_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerS.set_overlay_input_sagittal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerC.set_overlay_input_coronal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerA.render()
                    self.slice_viewerS.render()
                    self.slice_viewerC.render()
					
                elif id == 2:
                    if vf.isovalue_list.GetItem(1,0).IsChecked():
						#Remove red
                        self.slice_viewerA.set_overlay_input_axial_100band2(None)
                        self.slice_viewerS.set_overlay_input_sagittal_100band2(None)
                        self.slice_viewerC.set_overlay_input_coronal_100band2(None)
					
						#Add blue
                        self.slice_viewerA.set_overlay_input_axial_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                        self.slice_viewerS.set_overlay_input_sagittal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                        self.slice_viewerC.set_overlay_input_coronal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
						
						#Add red
                        self.slice_viewerA.set_overlay_input_axial_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerS.set_overlay_input_sagittal_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerC.set_overlay_input_coronal_100band2(self.isovalue_objs[id].band100["i{0}".format(self.isoline_sliders[1].GetValue())])
				
                    self.slice_viewerA.set_overlay_input_axial_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerS.set_overlay_input_sagittal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerC.set_overlay_input_coronal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    self.slice_viewerA.render()
                    self.slice_viewerS.render()
                    self.slice_viewerC.render()
		
		
            elif option == "50% band":
                for plan in range(len(self.planlist)):
                    self.balloon_axial.RemoveBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                    self.balloon_sagittal.RemoveBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                    self.balloon_coronal.RemoveBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
                    self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                    self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                    self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])	
                if id == 0:
                    if vf.isovalue_list.GetItem(1,0).IsChecked() and not vf.isovalue_list.GetItem(2,0).IsChecked():
						#Remove red
                        self.slice_viewerA.set_overlay_input_axial_50band2(None)
                        self.slice_viewerS.set_overlay_input_sagittal_50band2(None)
                        self.slice_viewerC.set_overlay_input_coronal_50band2(None)
					
						#Add yellow
                        self.slice_viewerA.set_overlay_input_axial_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
                        self.slice_viewerS.set_overlay_input_sagittal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
                        self.slice_viewerC.set_overlay_input_coronal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
						
						#Add red
                        self.slice_viewerA.set_overlay_input_axial_50band2(self.isovalue_objs[id].band50["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerS.set_overlay_input_sagittal_50band2(self.isovalue_objs[id].band50["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerC.set_overlay_input_coronal_50band2(self.isovalue_objs[id].band50["i{0}".format(self.isoline_sliders[1].GetValue())])
						
                    elif vf.isovalue_list.GetItem(2,0).IsChecked() and not vf.isovalue_list.GetItem(1,0).IsChecked():	
						#Remove blue
                        self.slice_viewerA.set_overlay_input_axial_50band3(None)
                        self.slice_viewerS.set_overlay_input_sagittal_50band3(None)
                        self.slice_viewerC.set_overlay_input_coronal_50band3(None)
					
						#Add yellow
                        self.slice_viewerA.set_overlay_input_axial_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
                        self.slice_viewerS.set_overlay_input_sagittal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
                        self.slice_viewerC.set_overlay_input_coronal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
						
						#Add blue
                        self.slice_viewerA.set_overlay_input_axial_50band3(self.isovalue_objs[id].band50["i{0}".format(self.isoline_sliders[2].GetValue())])
                        self.slice_viewerS.set_overlay_input_sagittal_50band3(self.isovalue_objs[id].band50["i{0}".format(self.isoline_sliders[2].GetValue())])
                        self.slice_viewerC.set_overlay_input_coronal_50band3(self.isovalue_objs[id].band50["i{0}".format(self.isoline_sliders[2].GetValue())])
						
                    elif vf.isovalue_list.GetItem(1,0).IsChecked() and vf.isovalue_list.GetItem(2,0).IsChecked():
					
						#Remove red
                        self.slice_viewerA.set_overlay_input_axial_50band2(None)
                        self.slice_viewerS.set_overlay_input_sagittal_50band2(None)
                        self.slice_viewerC.set_overlay_input_coronal_50band2(None)
					
						#Remove blue
                        self.slice_viewerA.set_overlay_input_axial_50band3(None)
                        self.slice_viewerS.set_overlay_input_sagittal_50band3(None)
                        self.slice_viewerC.set_overlay_input_coronal_50band3(None)
					
						#Add yellow
                        self.slice_viewerA.set_overlay_input_axial_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
                        self.slice_viewerS.set_overlay_input_sagittal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
                        self.slice_viewerC.set_overlay_input_coronal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
						
						#Add blue
                        self.slice_viewerA.set_overlay_input_axial_50band3(self.isovalue_objs[id].band50["i{0}".format(self.isoline_sliders[2].GetValue())])
                        self.slice_viewerS.set_overlay_input_sagittal_50band3(self.isovalue_objs[id].band50["i{0}".format(self.isoline_sliders[2].GetValue())])
                        self.slice_viewerC.set_overlay_input_coronal_50band3(self.isovalue_objs[id].band50["i{0}".format(self.isoline_sliders[2].GetValue())])
						
						#Add red
                        self.slice_viewerA.set_overlay_input_axial_50band2(self.isovalue_objs[id].band50["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerS.set_overlay_input_sagittal_50band2(self.isovalue_objs[id].band50["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerC.set_overlay_input_coronal_50band2(self.isovalue_objs[id].band50["i{0}".format(self.isoline_sliders[1].GetValue())])
					
						
                    self.slice_viewerA.set_overlay_input_axial_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
                    self.slice_viewerS.set_overlay_input_sagittal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
                    self.slice_viewerC.set_overlay_input_coronal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
                    self.slice_viewerA.render()
                    self.slice_viewerS.render()
                    self.slice_viewerC.render()
						
						
                elif id == 1:
                    self.slice_viewerA.set_overlay_input_axial_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
                    self.slice_viewerS.set_overlay_input_sagittal_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
                    self.slice_viewerC.set_overlay_input_coronal_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
                    self.slice_viewerA.render()
                    self.slice_viewerS.render()
                    self.slice_viewerC.render()
					
                elif id == 2:
                    if vf.isovalue_list.GetItem(1,0).IsChecked():
						#Remove red
                        self.slice_viewerA.set_overlay_input_axial_50band2(None)
                        self.slice_viewerS.set_overlay_input_sagittal_50band2(None)
                        self.slice_viewerC.set_overlay_input_coronal_50band2(None)
					
						#Add blue
                        self.slice_viewerA.set_overlay_input_axial_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
                        self.slice_viewerS.set_overlay_input_sagittal_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
                        self.slice_viewerC.set_overlay_input_coronal_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
						
						#Add red
                        self.slice_viewerA.set_overlay_input_axial_50band2(self.isovalue_objs[id].band50["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerS.set_overlay_input_sagittal_50band2(self.isovalue_objs[id].band50["i{0}".format(self.isoline_sliders[1].GetValue())])
                        self.slice_viewerC.set_overlay_input_coronal_50band2(self.isovalue_objs[id].band50["i{0}".format(self.isoline_sliders[1].GetValue())])
				
                    self.slice_viewerA.set_overlay_input_axial_100band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
                    self.slice_viewerS.set_overlay_input_sagittal_100band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
                    self.slice_viewerC.set_overlay_input_coronal_100band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
                    self.slice_viewerA.render()
                    self.slice_viewerS.render()
                    self.slice_viewerC.render()
		
            elif option == "Full contour boxplot":
                for plan in range(len(self.planlist)):
                    self.balloon_axial.RemoveBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                    self.balloon_sagittal.RemoveBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                    self.balloon_coronal.RemoveBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
                    self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                    self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                    self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
					
                self.renA.AddActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)])
                self.renS.AddActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)])
                self.renC.AddActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)])
                self.balloon_axial.AddBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))
                self.balloon_sagittal.AddBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))
                self.balloon_coronal.AddBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))
                 
                for outlier in outliers:
                    #color_outlier = self.ctf_yellow.GetColor(self.contours_info[isovalue][outlier][1])	
                    #self.isovalue_objs[id].set_outlier_contours_to_dark(outlier, color_outlier)
                    self.renA.AddActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(outlier)])
                    self.renS.AddActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(outlier)])
                    self.renC.AddActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(outlier)])
					
                if id == 0:
				    self.slice_viewerA.set_overlay_input_axial_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerS.set_overlay_input_sagittal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerC.set_overlay_input_coronal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                elif id == 1:
				    self.slice_viewerA.set_overlay_input_axial_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerS.set_overlay_input_sagittal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerC.set_overlay_input_coronal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                elif id == 2:
				    self.slice_viewerA.set_overlay_input_axial_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerS.set_overlay_input_sagittal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerC.set_overlay_input_coronal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
					
        else:
            for plan in range(len(self.planlist)):
                self.balloon_axial.RemoveBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                self.balloon_sagittal.RemoveBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                self.balloon_coronal.RemoveBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
                self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])

            if id == 0:
				self.slice_viewerA.set_overlay_input_axial_100band1(None)
				self.slice_viewerS.set_overlay_input_sagittal_100band1(None)
				self.slice_viewerC.set_overlay_input_coronal_100band1(None)
				
				self.slice_viewerA.set_overlay_input_axial_50band1(None)
				self.slice_viewerS.set_overlay_input_sagittal_50band1(None)
				self.slice_viewerC.set_overlay_input_coronal_50band1(None)
				
            elif id == 1:
				self.slice_viewerA.set_overlay_input_axial_100band2(None)
				self.slice_viewerS.set_overlay_input_sagittal_100band2(None)
				self.slice_viewerC.set_overlay_input_coronal_100band2(None)
				
				self.slice_viewerA.set_overlay_input_axial_50band2(None)
				self.slice_viewerS.set_overlay_input_sagittal_50band2(None)
				self.slice_viewerC.set_overlay_input_coronal_50band2(None)
            elif id == 2:
				self.slice_viewerA.set_overlay_input_axial_100band3(None)
				self.slice_viewerS.set_overlay_input_sagittal_100band3(None)
				self.slice_viewerC.set_overlay_input_coronal_100band3(None)
				
				self.slice_viewerA.set_overlay_input_axial_50band3(None)
				self.slice_viewerS.set_overlay_input_sagittal_50band3(None)
				self.slice_viewerC.set_overlay_input_coronal_50band3(None)
				
            self.balloon_axial.EnabledOff()
            self.balloon_sagittal.EnabledOff()
            self.balloon_coronal.EnabledOff()
				
        self.slice_viewerA.render()
        self.slice_viewerS.render()
        self.slice_viewerC.render()
        #event.Skip()

    def OnChooseBackground(self, event):

        id = event.GetEventObject().GetId()
        
        #colour = self.colors[id].GetColour().Get()
        colour = self.colors[id].GetValue()
		
		
        item = self._view_frame.isovalue_list.GetItem(id)
        item.SetBackgroundColour(colour)
        self._view_frame.isovalue_list.SetItem(item)
		
        for plan in range(len(self.planlist)):
            self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)].GetProperty().SetColor(colour)
			
        self.slice_viewerA.render()
        event.Skip()
	
	
	
    def OnComboBox(self,event):
	
        vf = self._view_frame
	
        id = event.GetEventObject().GetId()
		
        if not vf.isovalue_list.GetItem(id,0).IsChecked():
			return
		
        isovalue = self.isoline_sliders[id].GetValue()
        median = self.median_outliers_ids["i{0}".format(isovalue)][0]
        outliers = self.median_outliers_ids["i{0}".format(isovalue)][1]
		
        #probability = self.contours_info[isovalue][median][1]		
        #color_median = self.ctf_yellow.GetColor(probability)
		
        option = event.GetString()
		
        if id == 0:
            temp_ctf = self.ctf_yellow
            temp_median = self.median_purple
        elif id == 1:
            temp_ctf = self.ctf_red
            temp_median = self.median_green
        elif id == 2:
            temp_ctf = self.ctf_blue
            temp_median = self.median_orange
		
        if option == "Contours":
            if id == 0:
				self.slice_viewerA.set_overlay_input_axial_100band1(None)
				self.slice_viewerS.set_overlay_input_sagittal_100band1(None)
				self.slice_viewerC.set_overlay_input_coronal_100band1(None)
				self.slice_viewerA.set_overlay_input_axial_50band1(None)
				self.slice_viewerS.set_overlay_input_sagittal_50band1(None)
				self.slice_viewerC.set_overlay_input_coronal_50band1(None)
            elif id == 1:
				self.slice_viewerA.set_overlay_input_axial_100band2(None)
				self.slice_viewerS.set_overlay_input_sagittal_100band2(None)
				self.slice_viewerC.set_overlay_input_coronal_100band2(None)
				self.slice_viewerA.set_overlay_input_axial_50band2(None)
				self.slice_viewerS.set_overlay_input_sagittal_50band2(None)
				self.slice_viewerC.set_overlay_input_coronal_50band2(None)
            elif id == 2:
				self.slice_viewerA.set_overlay_input_axial_100band3(None)
				self.slice_viewerS.set_overlay_input_sagittal_100band3(None)
				self.slice_viewerC.set_overlay_input_coronal_100band3(None)
				self.slice_viewerA.set_overlay_input_axial_50band3(None)
				self.slice_viewerS.set_overlay_input_sagittal_50band3(None)
				self.slice_viewerC.set_overlay_input_coronal_50band3(None)
				
            for plan in range(len(self.planlist)):
                probability = self.contours_info[isovalue][plan][1]
                color = temp_ctf.GetColor(probability)
                opacity = self.otf.GetValue(probability)
                self.isovalue_objs[id].set_contours_color_and_pattern(plan, probability, color, opacity)
                self.renA.AddActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                self.renS.AddActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                self.renC.AddActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
                self.balloon_axial.AddBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)] ,'dose260-' + str(plan) + "\n" + "Isovalue" + str(isovalue))
                self.balloon_sagittal.AddBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)] ,'dose260-' + str(plan) + "\n" + "Isovalue" + str(isovalue))
                self.balloon_coronal.AddBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)] ,'dose260-' + str(plan) + "\n" + "Isovalue" + str(isovalue))

            self.isovalue_objs[id].set_contour_color(median, temp_median)
				
            self.balloon_axial.RemoveBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)])
            self.balloon_sagittal.RemoveBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)])
            self.balloon_coronal.RemoveBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)])
            self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)])
            self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)])
            self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)])
			
            #self.slice_viewerA.render()
			
            self.renA.AddActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)])
            self.renS.AddActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)])
            self.renC.AddActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)])
            self.balloon_axial.AddBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))
            self.balloon_sagittal.AddBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))
            self.balloon_coronal.AddBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))
			
            self.slice_viewerA.render()
			
        elif option == "Median":
            if id == 0:
				self.slice_viewerA.set_overlay_input_axial_100band1(None)
				self.slice_viewerS.set_overlay_input_sagittal_100band1(None)
				self.slice_viewerC.set_overlay_input_coronal_100band1(None)
				self.slice_viewerA.set_overlay_input_axial_50band1(None)
				self.slice_viewerS.set_overlay_input_sagittal_50band1(None)
				self.slice_viewerC.set_overlay_input_coronal_50band1(None)
            elif id == 1:
				self.slice_viewerA.set_overlay_input_axial_100band2(None)
				self.slice_viewerS.set_overlay_input_sagittal_100band2(None)
				self.slice_viewerC.set_overlay_input_coronal_100band2(None)
				self.slice_viewerA.set_overlay_input_axial_50band2(None)
				self.slice_viewerS.set_overlay_input_sagittal_50band2(None)
				self.slice_viewerC.set_overlay_input_coronal_50band2(None)
            elif id == 2:
				self.slice_viewerA.set_overlay_input_axial_100band3(None)
				self.slice_viewerS.set_overlay_input_sagittal_100band3(None)
				self.slice_viewerC.set_overlay_input_coronal_100band3(None)
				self.slice_viewerA.set_overlay_input_axial_50band3(None)
				self.slice_viewerS.set_overlay_input_sagittal_50band3(None)
				self.slice_viewerC.set_overlay_input_coronal_50band3(None)
            for plan in range(len(self.planlist)):
                self.balloon_axial.RemoveBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                self.balloon_sagittal.RemoveBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                self.balloon_coronal.RemoveBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
                self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
									
            self.isovalue_objs[id].set_contour_color(median, temp_median)    
            self.renA.AddActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)])
            self.renS.AddActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)])
            self.renC.AddActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)])
            self.balloon_axial.AddBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))
            self.balloon_sagittal.AddBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))
            self.balloon_coronal.AddBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))		
			
        elif option == "Bands":
            for plan in range(len(self.planlist)):
                self.balloon_axial.RemoveBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                self.balloon_sagittal.RemoveBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                self.balloon_coronal.RemoveBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
                self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])	
            if id == 0:
				#100%band
				self.slice_viewerA.set_overlay_input_axial_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				
				#50%band
				self.slice_viewerA.set_overlay_input_axial_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
            elif id == 1:
				self.slice_viewerA.set_overlay_input_axial_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				
				self.slice_viewerA.set_overlay_input_axial_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
            elif id == 2:
				self.slice_viewerA.set_overlay_input_axial_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				
				self.slice_viewerA.set_overlay_input_axial_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
		
        elif option == "50% band":
            for plan in range(len(self.planlist)):
                self.balloon_axial.RemoveBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                self.balloon_sagittal.RemoveBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                self.balloon_coronal.RemoveBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
                self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])	
            
            if id == 0:
				self.slice_viewerA.set_overlay_input_axial_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerA.set_overlay_input_axial_100band1(None)
				self.slice_viewerS.set_overlay_input_sagittal_100band1(None)
				self.slice_viewerC.set_overlay_input_coronal_100band1(None)
				
            elif id == 1:
				self.slice_viewerA.set_overlay_input_axial_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerA.set_overlay_input_axial_100band2(None)
				self.slice_viewerS.set_overlay_input_sagittal_100band2(None)
				self.slice_viewerC.set_overlay_input_coronal_100band2(None)
				
            elif id == 2:
				self.slice_viewerA.set_overlay_input_axial_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerA.set_overlay_input_axial_100band3(None)
				self.slice_viewerS.set_overlay_input_sagittal_100band3(None)
				self.slice_viewerC.set_overlay_input_coronal_100band3(None)
				
        elif option == "100% band":
            for plan in range(len(self.planlist)):
                self.balloon_axial.RemoveBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                self.balloon_sagittal.RemoveBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                self.balloon_coronal.RemoveBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
                self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])	
            
            if id == 0:
				self.slice_viewerA.set_overlay_input_axial_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerA.set_overlay_input_axial_50band1(None)
				self.slice_viewerS.set_overlay_input_sagittal_50band1(None)
				self.slice_viewerC.set_overlay_input_coronal_50band1(None)
				
            elif id == 1:
				self.slice_viewerA.set_overlay_input_axial_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerA.set_overlay_input_axial_50band2(None)
				self.slice_viewerS.set_overlay_input_sagittal_50band2(None)
				self.slice_viewerC.set_overlay_input_coronal_50band2(None)
				
            elif id == 2:
				self.slice_viewerA.set_overlay_input_axial_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerA.set_overlay_input_axial_50band3(None)
				self.slice_viewerS.set_overlay_input_sagittal_50band3(None)
				self.slice_viewerC.set_overlay_input_coronal_50band3(None)
		
        elif option == "Outliers":
            if id == 0:
				self.slice_viewerA.set_overlay_input_axial_100band1(None)
				self.slice_viewerS.set_overlay_input_sagittal_100band1(None)
				self.slice_viewerC.set_overlay_input_coronal_100band1(None)
				self.slice_viewerA.set_overlay_input_axial_50band1(None)
				self.slice_viewerS.set_overlay_input_sagittal_50band1(None)
				self.slice_viewerC.set_overlay_input_coronal_50band1(None)
            elif id == 1:
				self.slice_viewerA.set_overlay_input_axial_100band2(None)
				self.slice_viewerS.set_overlay_input_sagittal_100band2(None)
				self.slice_viewerC.set_overlay_input_coronal_100band2(None)
				self.slice_viewerA.set_overlay_input_axial_50band2(None)
				self.slice_viewerS.set_overlay_input_sagittal_50band2(None)
				self.slice_viewerC.set_overlay_input_coronal_50band2(None)
            elif id == 2:
				self.slice_viewerA.set_overlay_input_axial_100band3(None)
				self.slice_viewerS.set_overlay_input_sagittal_100band3(None)
				self.slice_viewerC.set_overlay_input_coronal_100band3(None)
				self.slice_viewerA.set_overlay_input_axial_50band3(None)
				self.slice_viewerS.set_overlay_input_sagittal_50band3(None)
				self.slice_viewerC.set_overlay_input_coronal_50band3(None)
            for plan in range(len(self.planlist)):
                self.balloon_axial.RemoveBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                self.balloon_sagittal.RemoveBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                self.balloon_coronal.RemoveBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
                self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
            for outlier in outliers:
                self.renA.AddActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(outlier)])
                self.renS.AddActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(outlier)])
                self.renC.AddActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(outlier)])
                self.balloon_axial.AddBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(outlier)] ,'dose260-' + str(outlier) + "\n" + "Isovalue" + str(isovalue))
                self.balloon_sagittal.AddBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(outlier)] ,'dose260-' + str(outlier) + "\n" + "Isovalue" + str(isovalue))
                self.balloon_coronal.AddBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(outlier)] ,'dose260-' + str(outlier) + "\n" + "Isovalue" + str(isovalue))				
		
        elif option == "Full contour boxplot":
            for plan in range(len(self.planlist)):
                self.balloon_axial.RemoveBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                self.balloon_sagittal.RemoveBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                self.balloon_coronal.RemoveBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
                self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
            
            if id == 0:
				self.slice_viewerA.set_overlay_input_axial_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerA.set_overlay_input_axial_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
            elif id == 1:
				self.slice_viewerA.set_overlay_input_axial_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerA.set_overlay_input_axial_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
            elif id == 2:
				self.slice_viewerA.set_overlay_input_axial_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				self.slice_viewerA.set_overlay_input_axial_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerS.set_overlay_input_sagittal_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				self.slice_viewerC.set_overlay_input_coronal_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
			
            self.isovalue_objs[id].set_contour_color(median, temp_median)  
            self.renA.AddActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)])
            self.renS.AddActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)])
            self.renC.AddActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)])
            self.balloon_axial.AddBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))
            self.balloon_sagittal.AddBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))
            self.balloon_coronal.AddBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))
			
            for outlier in outliers:
                #color_outlier = self.ctf_yellow.GetColor(self.contours_info[isovalue][outlier][1])	
                #self.isovalue_objs[id].set_outlier_contours_to_dark(outlier, color_outlier)
                self.renA.AddActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(outlier)])
                self.renS.AddActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(outlier)])
                self.renC.AddActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(outlier)])
                self.balloon_axial.AddBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(outlier)] ,'dose260-' + str(outlier) + "\n" + "Isovalue" + str(isovalue))
                self.balloon_sagittal.AddBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(outlier)] ,'dose260-' + str(outlier) + "\n" + "Isovalue" + str(isovalue))
                self.balloon_coronal.AddBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(outlier)] ,'dose260-' + str(outlier) + "\n" + "Isovalue" + str(isovalue))				
		
        self.slice_viewerA.render()
        self.slice_viewerS.render()
        self.slice_viewerC.render()
        #event.Skip()
		
		
		
    def OnRadioButton(self,event):
		id = event.GetEventObject().GetId()
		self.radio_id = id
		
				
			
    def OnSave(self,event):
        """Handler for file saving
        """
        filters = 'Binary files (*.dat)|*.dat;'
        dlg = wx.FileDialog(self._view_frame, "Save as", "", "", filters, wx.FD_SAVE)
        if dlg.ShowModal() == wx.ID_OK:
            self.volume_path = dlg.GetPath()
            save_file = open(self.volume_path, 'wb')
            pickle.dump(self._view_frame.patients, save_file)
            save_file.close()
        dlg.Destroy()
		
    def OnOpen(self,event):
        """Handler for file opening
        """
        filters = 'Binary files (*.dat)|*.dat;'
        dlg = wx.FileDialog(self._view_frame, "Load patient data", "", "", filters, wx.FD_OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.volume_path = dlg.GetPath()
            load_file = open(self.volume_path, 'rb')
            loaded_patient_data = pickle.load(load_file)
            load_file.close()
            self._view_frame.patients.update(loaded_patient_data)
            for k,v in loaded_patient_data.items():
                #t = (str(k), os.path.split(v[0])[1], str(len(v[1])))
                idx = self._view_frame.patient_list.InsertStringItem(sys.maxint, str(k))
                self._view_frame.patient_list.SetStringItem(idx, 1, os.path.split(v[0])[1])
                self._view_frame.patient_list.SetStringItem(idx, 2, str(len(v[1])))
                #print(t)
                #self._view_frame.patient_list.SetItemData(idx,idx)
                #self._view_frame.itemDataMap[idx] = t
                #print(t)
            #print(self._view_frame.patients)
			#print(loaded_game_data)
        dlg.Destroy()
	
	
    def selectionCallback(self,caller,event):

        #min_isovalue = min(self.contours_info.iteritems(), key=operator.itemgetter(1))[0]
        min_isovalue = min(self.contours_info)
        ids = self._view_frame.chart.GetPlot(0).GetSelection()
        #self._view_frame.plot.SetColor(0,255,255,255)
        print(str(self._view_frame.plot.GetBarsCount()))
        for i in range(ids.GetNumberOfTuples()):
            print(ids.GetValue(i))
			
    def _show_overlay(self,event):
	
        vf = self._view_frame
        
        if vf.show_overlay.IsChecked():
		
			if str(vf.radio_mean.GetValue()) == "True":
				#Activate color map for mean
				self.slice_viewerA.overlay_ipws[0].SetLookupTable(self.lut_mean)
				self.slice_viewerS.overlay_ipws[1].SetLookupTable(self.lut_mean)
				self.slice_viewerC.overlay_ipws[2].SetLookupTable(self.lut_mean)
				self.slice_viewerA.set_overlay_input(self.plandata)
				self.slice_viewerC.set_overlay_inputC(self.plandata)
				self.slice_viewerS.set_overlay_inputS(self.plandata)
			else:
				#Activate color map for std
				self.slice_viewerA.overlay_ipws[0].SetLookupTable(self.lut_std)
				self.slice_viewerS.overlay_ipws[1].SetLookupTable(self.lut_std)
				self.slice_viewerC.overlay_ipws[2].SetLookupTable(self.lut_std)
				self.slice_viewerA.set_overlay_input(self.stddata)
				self.slice_viewerC.set_overlay_inputC(self.stddata)
				self.slice_viewerS.set_overlay_inputS(self.stddata)
        else:
			self.slice_viewerA.set_overlay_input(None)
			self.slice_viewerC.set_overlay_inputC(None)
			self.slice_viewerS.set_overlay_inputS(None)
		
        self.slice_viewerA.render()
        self.slice_viewerC.render()
        self.slice_viewerS.render()		
	
    def _initialize_boxplot(self):
        
        self.read_isovalues_files('.\\isovaluesadc')	

        self._view_frame.SetStatusText( "Processing contour boxplot...")	
		
        for k,v in self.isovalues.items():
    
            contour_ids = self.calculate_cb_contours(k, v[0])
            self.median_outliers_ids[k] = contour_ids
    
            self.calculate_50band(k, v[2])
            self.calculate_100band(k, v[1])
        #print(self.isovalues_barplot)
        #self.isovalues_barplot.sort()
        #print(self.contours_info)
        self.create_csv_file()
        self._view_frame.SetStatusText( "Finished Boxplot...")
		

    def calculate_cb_contours(self,isovalue, filepath):
    
        analysis = open(filepath)    
    
        ids = []
        ranking = {}
		
		
		
        line = analysis.readline()
    
        while line:
            sline = line.strip().split()
    
            key = int(sline[1])
            value = float(sline[0])
    
            ranking.update({key : value})
    
            line = analysis.readline()
    
        median_contour_id = max(ranking.iteritems(), key=operator.itemgetter(1))[0]
        outliers_ids = [k for k,v in ranking.items() if v==0.0]    
    
        contours = [[k,v] for k,v in ranking.iteritems()] 
		
        iso = int(re.findall('\d+|\D+', isovalue)[1])
		
        self.contours_info.update({iso : contours})
	
        ids.append(median_contour_id)
        ids.append(outliers_ids) 
		
        highest_probability = max(ranking.iteritems(), key=operator.itemgetter(1))[1]
		
        uncertainty = highest_probability
		
        nr_outliers = len(outliers_ids)
		
		
        self.barplot_data.update({iso : uncertainty})
		
        self.isovalues_barplot.append(iso)
        #self.band_depths.append(uncertainty)
		
        return ids

		
		
    def read_isovalues_files(self,dir):           	
        subdirs = [x[0] for x in os.walk(dir)]                                                                            
    
        for subdir in subdirs:               
			f = []
			if len(re.findall('\d+|\D+', os.path.split(subdir)[1])) == 1:
				continue
        
			index = int(re.findall('\d+|\D+', os.path.split(subdir)[1])[1])
                                    
			files = os.walk(subdir).next()[2]               
			if (len(files) > 0):                                                                                          
				for file in files:                                                                                        
					f.append(subdir + "\\" + file)   
					
			self.isovalues["i{0}".format(index)] = f
			

    def calculate_50band(self,k,filepath):
    
        reader50 = vtk.vtkXMLImageDataReader()
        reader50.SetFileName(filepath)
        reader50.Update()
        
        #Flip the Y-axis of the image
        flipYFilter50 = vtk.vtkImageFlip()
        flipYFilter50.SetFilteredAxis(1) # Specify which axis will be flipped. 0 for x, 1 for y and 2 for z. 
        flipYFilter50.SetInput(reader50.GetOutput())
        flipYFilter50.Update()

        self.image_data50[k] = self.put_volume_at_origin2(flipYFilter50.GetOutput())
	
	
    def calculate_100band(self, k, filepath):
    
        reader100 = vtk.vtkXMLImageDataReader()
        reader100.SetFileName(filepath)
        reader100.Update()
        
        flipYFilter100 = vtk.vtkImageFlip()
        flipYFilter100.SetFilteredAxis(1) 
        flipYFilter100.SetInput(reader100.GetOutput())
        flipYFilter100.Update()

        self.image_data100[k] = self.put_volume_at_origin2(flipYFilter100.GetOutput())
		
				
    def analyse_checkboxes_isovalue(self, sliceA_index, sliceS_index, sliceC_index):
		
        vf = self._view_frame

        for id in range(vf.isovalue_list.GetItemCount()):
			
            isovalue = self.isoline_sliders[id].GetValue()
            option = self.options[id].GetValue()
			
            median = self.median_outliers_ids["i{0}".format(isovalue)][0]
            outliers = self.median_outliers_ids["i{0}".format(isovalue)][1]
		
            if vf.isovalue_list.GetItem(id,0).IsChecked():
                if id == 0:
                    temp_ctf = self.ctf_yellow
                    temp_median = self.median_purple
                elif id == 1:
                    temp_ctf = self.ctf_red
                    temp_median = self.median_green
                elif id == 2:
                    temp_ctf = self.ctf_blue
                    temp_median = self.median_orange
			
                for plan in range(len(self.planlist)):
                    probability = self.contours_info[isovalue][plan][1]
                    color = temp_ctf.GetColor(probability)
                    opacity = self.otf.GetValue(probability)
                    self.isovalue_objs[id].setup_isoline_actors(plan,sliceA_index,sliceS_index,sliceC_index,isovalue, color, opacity)
					
                if option == "Contours":
                    if id == 0:
				        self.slice_viewerA.set_overlay_input_axial_100band1(None)
				        self.slice_viewerS.set_overlay_input_sagittal_100band1(None)
				        self.slice_viewerC.set_overlay_input_coronal_100band1(None)
                    elif id == 1:
				        self.slice_viewerA.set_overlay_input_axial_100band2(None)
				        self.slice_viewerS.set_overlay_input_sagittal_100band2(None)
				        self.slice_viewerC.set_overlay_input_coronal_100band2(None)
                    elif id == 2:
				        self.slice_viewerA.set_overlay_input_axial_100band3(None)
				        self.slice_viewerS.set_overlay_input_sagittal_100band3(None)
				        self.slice_viewerC.set_overlay_input_coronal_100band3(None)		
                    for plan in range(len(self.planlist)):
                        self.renA.AddActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                        self.renS.AddActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                        self.renC.AddActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
					
                    self.isovalue_objs[id].set_contour_color(median, temp_median)
        
                elif option == "Median":
                    if id == 0:
				        self.slice_viewerA.set_overlay_input_axial_100band1(None)
				        self.slice_viewerS.set_overlay_input_sagittal_100band1(None)
				        self.slice_viewerC.set_overlay_input_coronal_100band1(None)
                    elif id == 1:
				        self.slice_viewerA.set_overlay_input_axial_100band2(None)
				        self.slice_viewerS.set_overlay_input_sagittal_100band2(None)
				        self.slice_viewerC.set_overlay_input_coronal_100band2(None)
                    elif id == 2:
				        self.slice_viewerA.set_overlay_input_axial_100band3(None)
				        self.slice_viewerS.set_overlay_input_sagittal_100band3(None)
				        self.slice_viewerC.set_overlay_input_coronal_100band3(None)
            
                    for plan in range(len(self.planlist)):
                        self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                        self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                        self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])		
					
                    self.renA.AddActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)])
                    self.renS.AddActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)])
                    self.renC.AddActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)])	
					
                    self.isovalue_objs[id].set_contour_color(median, temp_median)
			
                elif option == "Bands":
                    for plan in range(len(self.planlist)):
                        self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                        self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                        self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])	
                    if id == 0:
				        self.slice_viewerA.set_overlay_input_axial_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				        self.slice_viewerS.set_overlay_input_sagittal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				        self.slice_viewerC.set_overlay_input_coronal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    elif id == 1:
				        self.slice_viewerA.set_overlay_input_axial_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				        self.slice_viewerS.set_overlay_input_sagittal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				        self.slice_viewerC.set_overlay_input_coronal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    elif id == 2:
				        self.slice_viewerA.set_overlay_input_axial_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				        self.slice_viewerS.set_overlay_input_sagittal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				        self.slice_viewerC.set_overlay_input_coronal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
		
                elif option == "Outliers":
                    if id == 0:
				        self.slice_viewerA.set_overlay_input_axial_100band1(None)
				        self.slice_viewerS.set_overlay_input_sagittal_100band1(None)
				        self.slice_viewerC.set_overlay_input_coronal_100band1(None)
                    elif id == 1:
				        self.slice_viewerA.set_overlay_input_axial_100band2(None)
				        self.slice_viewerS.set_overlay_input_sagittal_100band2(None)
				        self.slice_viewerC.set_overlay_input_coronal_100band2(None)
                    elif id == 2:
				        self.slice_viewerA.set_overlay_input_axial_100band3(None)
				        self.slice_viewerS.set_overlay_input_sagittal_100band3(None)
				        self.slice_viewerC.set_overlay_input_coronal_100band3(None)
            
                    for plan in range(len(self.planlist)):
                        self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                        self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                        self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
            
                    for outlier in outliers:
                        color_outlier = self.ctf_yellow.GetColor(self.contours_info[isovalue][outlier][1])	
                        self.isovalue_objs[id].set_outlier_contours_to_dark(outlier, color_outlier)
                        self.renA.AddActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(outlier)])
                        self.renS.AddActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(outlier)])
                        self.renC.AddActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(outlier)])	
		
                elif option == "Full contour boxplot":
		
                    for plan in range(len(self.planlist)):
                        self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                        self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                        self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
            
                    self.renA.AddActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)])
                    self.renS.AddActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)])
                    self.renC.AddActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)])
					
                    self.isovalue_objs[id].set_contour_color(median, temp_median)
            
                    for outlier in outliers:
                        color_outlier = self.ctf_yellow.GetColor(self.contours_info[isovalue][outlier][1])	
                        self.isovalue_objs[id].set_outlier_contours_to_dark(outlier, color_outlier)
                        self.renA.AddActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(outlier)])
                        self.renS.AddActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(outlier)])
                        self.renC.AddActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(outlier)])	
				
                    if id == 0:
				        self.slice_viewerA.set_overlay_input_axial_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				        self.slice_viewerS.set_overlay_input_sagittal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				        self.slice_viewerC.set_overlay_input_coronal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    elif id == 1:
				        self.slice_viewerA.set_overlay_input_axial_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				        self.slice_viewerS.set_overlay_input_sagittal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				        self.slice_viewerC.set_overlay_input_coronal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
                    elif id == 2:
				        self.slice_viewerA.set_overlay_input_axial_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				        self.slice_viewerS.set_overlay_input_sagittal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				        self.slice_viewerC.set_overlay_input_coronal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
					
            else:
                for plan in range(len(self.planlist)):
                    self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(plan)])
                    self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(plan)])
                    self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(plan)])
					
                if id == 0:
				    self.slice_viewerA.set_overlay_input_axial_100band1(None)
				    self.slice_viewerS.set_overlay_input_sagittal_100band1(None)
				    self.slice_viewerC.set_overlay_input_coronal_100band1(None)
                elif id == 1:
				    self.slice_viewerA.set_overlay_input_axial_100band2(None)
				    self.slice_viewerS.set_overlay_input_sagittal_100band2(None)
				    self.slice_viewerC.set_overlay_input_coronal_100band2(None)
                elif id == 2:
				    self.slice_viewerA.set_overlay_input_axial_100band3(None)
				    self.slice_viewerS.set_overlay_input_sagittal_100band3(None)
				    self.slice_viewerC.set_overlay_input_coronal_100band3(None)	
				
    def _change_isovalue_multiple(self,event,control_id):
	    
		# 1 is the id for the slider
		# 2 is the id for the spin
		
        vf = self._view_frame
		
        id = event.GetEventObject().GetId()
		
        option = self.options[id].GetValue()
		
        if control_id == 1:
            self.isoline_spins[id].SetValue(self.isoline_sliders[id].GetValue())
            isovalue = self.isoline_spins[id].GetValue()
        elif control_id == 2:
            self.isoline_sliders[id].SetValue(self.isoline_spins[id].GetValue())
            isovalue = self.isoline_sliders[id].GetValue()
		
        color = self._view_frame.isovalue_list.GetItem(id).GetBackgroundColour()
			
        color_list = list(color)
			
        float_color = [round(c/255,3) for c in color_list]
			
        index = self.dic_iso_to_index[isovalue]
		
        #self.bars[index].set_facecolor(float_color)
        
        before = self.bars[index - 1].get_facecolor()
        current = self.bars[index].get_facecolor()
        after = self.bars[index + 1].get_facecolor()
		
        tempy = [1,1,0.0] #yellow
        tempr = [1,0.0,0.0] #red
        tempb = [0,0.643,0.941] #blue
		
        if float_color == tempy:
			if before == self.primary_colors_float_tuple[1]:
				self.bars[index - 1].set_facecolor(self.primary_colors_float_tuple[1])
			elif before == self.primary_colors_float_tuple[2]:
				self.bars[index - 1].set_facecolor(self.primary_colors_float_tuple[2])		
			else:
				self.bars[index - 1].set_facecolor(self.default_barcolor)
				
			if current == self.primary_colors_float_tuple[1]:
				self.bars[index].set_facecolor(self.primary_colors_float_tuple[1])
				#self.bars[index].set_facecolor('orange')
			elif current == self.primary_colors_float_tuple[2]:
				self.bars[index].set_facecolor(self.primary_colors_float_tuple[2])		
			else:
				self.bars[index].set_facecolor(float_color)
			
			if after == self.primary_colors_float_tuple[1]:
				self.bars[index + 1].set_facecolor(self.primary_colors_float_tuple[1])
			elif after == self.primary_colors_float_tuple[2]:
				self.bars[index + 1].set_facecolor(self.primary_colors_float_tuple[2])
			else:
				self.bars[index + 1].set_facecolor(self.default_barcolor)
			
        elif float_color == tempr:
			if before == self.primary_colors_float_tuple[0]:
				self.bars[index - 1].set_facecolor(self.primary_colors_float_tuple[0])
			elif before == self.primary_colors_float_tuple[2]:
				self.bars[index - 1].set_facecolor(self.primary_colors_float_tuple[2])		
			else:
				self.bars[index - 1].set_facecolor(self.default_barcolor)
				
			if current == self.primary_colors_float_tuple[0]:
				self.bars[index].set_facecolor(self.primary_colors_float_tuple[0])	
			elif current == self.primary_colors_float_tuple[2]:
				self.bars[index].set_facecolor(self.primary_colors_float_tuple[2])		
			else:
				self.bars[index].set_facecolor(float_color)
			
			if after == self.primary_colors_float_tuple[0]:
				self.bars[index + 1].set_facecolor(self.primary_colors_float_tuple[0])
			elif after == self.primary_colors_float_tuple[2]:
				self.bars[index + 1].set_facecolor(self.primary_colors_float_tuple[2])
			else:
				self.bars[index + 1].set_facecolor(self.default_barcolor)
        elif float_color == tempb:
			if before == self.primary_colors_float_tuple[0]:
				self.bars[index - 1].set_facecolor(self.primary_colors_float_tuple[0])
			elif before == self.primary_colors_float_tuple[1]:
				self.bars[index - 1].set_facecolor(self.primary_colors_float_tuple[1])		
			else:
				self.bars[index - 1].set_facecolor(self.default_barcolor)
				
			if current == self.primary_colors_float_tuple[0]:
				self.bars[index].set_facecolor(self.primary_colors_float_tuple[0])
			elif current == self.primary_colors_float_tuple[1]:
				self.bars[index].set_facecolor(self.primary_colors_float_tuple[1])		
			else:
				self.bars[index].set_facecolor(float_color)
			
			if after == self.primary_colors_float_tuple[0]:
				self.bars[index + 1].set_facecolor(self.primary_colors_float_tuple[0])
			elif after == self.primary_colors_float_tuple[1]:
				self.bars[index + 1].set_facecolor(self.primary_colors_float_tuple[1])
			else:
				self.bars[index + 1].set_facecolor(self.default_barcolor)
		
				
        median = self.median_outliers_ids["i{0}".format(isovalue)][0]
        outliers = self.median_outliers_ids["i{0}".format(isovalue)][1]	
		
        self.isovalue_objs[id].set_isovalue(isovalue)
		
        if id == 0:
            temp_ctf = self.ctf_yellow
        elif id == 1:
            temp_ctf = self.ctf_red
        elif id == 2:
            temp_ctf = self.ctf_blue
		
		
        for plan in range(len(self.planlist)):
            probability = self.contours_info[isovalue][plan][1]
            color = temp_ctf.GetColor(probability)
            opacity = self.otf.GetValue(probability)
            self.isovalue_objs[id].set_contours_color_and_pattern(plan, probability, color, opacity)
		
		#Use different colors for the median??
        if id == 0:
            self.isovalue_objs[id].set_contour_color(median, self.median_purple)        
        elif id == 1:
            self.isovalue_objs[id].set_contour_color(median, self.median_green)
        elif id == 2:
            self.isovalue_objs[id].set_contour_color(median, self.median_orange)
			
        #self.isovalue_objs[id].set_contour_color(median, temp_median)
			
        if vf.isovalue_list.GetItem(id,0).IsChecked():
            if option == "Bands" or option == "Full contour boxplot":
                if id == 0:
				    self.slice_viewerA.set_overlay_input_axial_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerS.set_overlay_input_sagittal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerC.set_overlay_input_coronal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
					
				    self.slice_viewerA.set_overlay_input_axial_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				    self.slice_viewerS.set_overlay_input_sagittal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				    self.slice_viewerC.set_overlay_input_coronal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
					
                if id == 1:
				    self.slice_viewerA.set_overlay_input_axial_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerS.set_overlay_input_sagittal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerC.set_overlay_input_coronal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
					
				    self.slice_viewerA.set_overlay_input_axial_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				    self.slice_viewerS.set_overlay_input_sagittal_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				    self.slice_viewerC.set_overlay_input_coronal_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
					
                if id == 2:
				    self.slice_viewerA.set_overlay_input_axial_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerS.set_overlay_input_sagittal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerC.set_overlay_input_coronal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
					
				    self.slice_viewerA.set_overlay_input_axial_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				    self.slice_viewerS.set_overlay_input_sagittal_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				    self.slice_viewerC.set_overlay_input_coronal_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
					
            elif option == "50% band":
                if id == 0:
				    self.slice_viewerA.set_overlay_input_axial_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				    self.slice_viewerS.set_overlay_input_sagittal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				    self.slice_viewerC.set_overlay_input_coronal_50band1(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
					
                if id == 1:
				    self.slice_viewerA.set_overlay_input_axial_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				    self.slice_viewerS.set_overlay_input_sagittal_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				    self.slice_viewerC.set_overlay_input_coronal_50band2(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
					
                if id == 2:
				    self.slice_viewerA.set_overlay_input_axial_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				    self.slice_viewerS.set_overlay_input_sagittal_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
				    self.slice_viewerC.set_overlay_input_coronal_50band3(self.isovalue_objs[id].band50["i{0}".format(isovalue)])
					
            elif option == "100% band":
                if id == 0:
				    self.slice_viewerA.set_overlay_input_axial_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerS.set_overlay_input_sagittal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerC.set_overlay_input_coronal_100band1(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
					
                if id == 1:
				    self.slice_viewerA.set_overlay_input_axial_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerS.set_overlay_input_sagittal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerC.set_overlay_input_coronal_100band2(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
					
                if id == 2:
				    self.slice_viewerA.set_overlay_input_axial_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerS.set_overlay_input_sagittal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
				    self.slice_viewerC.set_overlay_input_coronal_100band3(self.isovalue_objs[id].band100["i{0}".format(isovalue)])
            elif option == "Contours" or option == "Median":
                self.balloon_axial.RemoveBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)])
                self.balloon_sagittal.RemoveBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)])
                self.balloon_coronal.RemoveBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)])
                self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)])
                self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)])
                self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)])
		
                self.renA.AddActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)])
                self.renS.AddActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)])
                self.renC.AddActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)])
                self.balloon_axial.AddBalloon(self.isovalue_objs[id].contour_actors_axial["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))
                self.balloon_sagittal.AddBalloon(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))
                self.balloon_coronal.AddBalloon(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(median)] ,'dose260-' + str(median) + "\n" + "Isovalue" + str(isovalue))
				
        self._view_frame.canvasb.draw()
        self.slice_viewerA.render()
        self.slice_viewerC.render()
        self.slice_viewerS.render()
        #event.Skip()
				
				
    def _change_contour_color(self, event = None):
        """Handler for color adjustment (Color of selection)
        """
        for plan in range(len(self.planlist)):
            self.contour_actors["c{0}".format(plan)].GetProperty().SetColor(self._view_frame.color_picker.GetColour().Get())
        self.slice_viewerA.render()
		
		
    def onPicksquare(self,event):
	
        vf = self._view_frame
        ix, iy = event.xdata, event.ydata
		
        if self.count < 1:
            self.dc = datacursor(hover=True, axes = vf.axh, keybindings=dict(hide='h', toggle='e'), formatter = lambda **d: "Isovalue: {:.0f}\nDosePlan: {:.0f}\nProbability: {:.4f}".format(d["x"] + 70,self.nr_doseplans - d["y"],d["z"]))  
		
        plan = int(round(self.nr_doseplans - iy,0))
        iso = int(ix + 70)
				
        if self.isovalue_objs:
            probability = self.contours_info[iso][plan][1]
            color = self.ctf_yellow.GetColor(probability)
            opacity = self.otf.GetValue(probability)
			
            idx_axial = self.slice_viewerA.ipws[0].GetSliceIndex()
            idx_sagittal = self.slice_viewerS.ipws[1].GetSliceIndex()
            idx_coronal = self.slice_viewerC.ipws[2].GetSliceIndex()
			
            for id in range(0,3):
				for dp in range(len(self.planlist)):
					self.renA.RemoveActor(self.isovalue_objs[id].contour_actors_axial["c{0}".format(dp)])
					self.renS.RemoveActor(self.isovalue_objs[id].contour_actors_sagittal["c{0}".format(dp)])
					self.renC.RemoveActor(self.isovalue_objs[id].contour_actors_coronal["c{0}".format(dp)])
		
            self.isovalue_objs[0].setup_isoline_actors(plan,idx_axial,idx_sagittal,idx_coronal,iso, color, opacity)
            self.isovalue_objs[0].set_isovalue(iso)
            self.renA.AddActor(self.isovalue_objs[0].contour_actors_axial["c{0}".format(plan)])
            self.renS.AddActor(self.isovalue_objs[0].contour_actors_sagittal["c{0}".format(plan)])
            self.renC.AddActor(self.isovalue_objs[0].contour_actors_coronal["c{0}".format(plan)])
        else:
            dial = wx.MessageDialog(None, 'Please select a bar first.', 'Warning on heatmap', wx.OK | wx.ICON_EXCLAMATION)
            dial.ShowModal()
		
        #print 'doseplan = %d, isovalue = %d'%(dp, iso)
		
        self.slice_viewerA.render()
        self.slice_viewerS.render()
        self.slice_viewerC.render()
		
        self.count += 1
		
		
    def distPlot(self,point):
	
        self._view_frame.ax_violin.cla()
        self._view_frame.ax_violin.set_xlabel("Voxel values")
        self._view_frame.ax_violin.set_ylabel("Density")
        self._view_frame.ax_violin.set_xlim(60, 120)
        self._view_frame.ax_violin.set_ylim(0, 0.3)
		
        p = np.array(point)
        x = p[0]
        y = p[1]
        z = p[2]
		
        yaxis = []
        xaxis = []
		
        if len(self.planlist)>1:
            for j in range(self.nr_doseplans):
                i = self.doseplans["p{0}".format(j)].GetScalarComponentAsDouble(x, y, z, 0)
                yaxis.append(i)
                xaxis.append("DosePlan %s" %(j))
		
        voxels = np.array(yaxis)
        doseplans = np.array(xaxis)
		
        sns.distplot(voxels, rug=True, hist=False, ax=self._view_frame.ax_violin)
        
        self._view_frame.canvas_violin.draw()
        self._view_frame.canvas_scatter.draw_idle()
	
    def scatterPlot(self):
	
        self.points = self._view_frame.ax_scatter.scatter(self.meanx, self.stdy, s = 20, marker='o', c='b', lw = 0.4, picker = 5)
		
        viewer = self
        self.selector = SelectFromCollection(viewer, self._view_frame.ax_scatter, self.points)
		
        x = np.array(self.meanx)
        y = np.array(self.stdy)
		
        sns.kdeplot(x, y, cmap = 'autumn', bw = 'silverman', shade=False, shade_lowest=False, ax=self._view_frame.ax_scatter, kwargs={'line_kws':{'color':'cyan'}})
        self._view_frame.canvas_scatter.draw()
		
    def refresh_2d(self, data):
		#lut_red
        self.slice_viewerA.overlay_ipws_voxels[0].SetLookupTable(self.lut_bar)
        self.slice_viewerA.set_overlay_input_voxels(data)
        self.slice_viewerA.render()
		
    def refresh_3d(self):
        self._view_frame.interactor3d.Render()
		
		
    def heatMap(self):
        #sns.set(font_scale=2.5)
        doseplans = pd.read_csv('C:\\Users\\pedro_000\\Desktop\\EnsembleViewerFinal\\heatmap.csv')
        doseplans_data = doseplans.pivot("Doseplans", "Isodose", "Probabilities")
        cmap = sns.light_palette("#4d4d4d", as_cmap=True, reverse = True)
        g = sns.heatmap(doseplans_data, vmin=0, vmax=1, ax = self._view_frame.axh, cbar = True, annot=False, cmap=cmap, picker = True)
        
        for item in g.get_yticklabels():
            item.set_rotation(0)
            item.set_size(14)
		
        self._view_frame.canvash.draw()
	
    def BarPlotwithData(self):
        
        #self._view_frame.ax.cla()
        #self._view_frame.axb.clear()
        self._view_frame.axb.grid(True)		
		
        indexes = []
		
        #self._view_frame.canvas1.SetToolTip(self._view_frame.tooltip)
        #self._view_frame.tooltip.Enable(True)
        #self._view_frame.tooltip.SetDelay(0)
        self._view_frame.canvasb.mpl_connect('pick_event', self.on_pick)
        self._view_frame.canvasb.mpl_connect('motion_notify_event', self.on_focus)
		
        d = collections.OrderedDict(sorted(self.barplot_data.items()))
		
        yaxis = []

        for k,v in d.items():
            yaxis.append(v)
		
        self.isovalues_barplot.sort()
		
        self.xaxis = np.array(self.isovalues_barplot)
        self.yaxis = np.array(yaxis)
		
        #sns.barplot(self.xaxis, self.yaxis, palette="BuGn_d", ax=self._view_frame.ax, picker = 2)
        self.bars = self._view_frame.axb.bar(self.xaxis, self.yaxis, align='center', picker=0.5)
		
        for bar in self.bars:
            bar.set_facecolor('black')
		
        self.default_barcolor = self.bars[0].get_facecolor()
		
        for i in range(0,len(self.bars)):
            indexes.append(i)
		
        #print(self.isovalues_barplot)
        #print(indexes)
		
        for iso, index in zip(self.isovalues_barplot, indexes):
            self.dic_iso_to_index[iso] = index
		
        #print(self.dic_iso_to_index)
		
        #self._view_frame.canvas1.mpl_connect('motion_notify_event', self.view_frame._onMotion)
        #self._view_frame.canvas1.mpl_connect('pick_event', self.onPick)
		
        self._view_frame.canvasb.draw()

    def on_focus(self,event): 
        if not event.inaxes: 
            return 
        under = self._view_frame.axb.hitlist(event)
    
        enter = [a for a in under if a not in self.active]
        leave = [a for a in self.active if a not in under]
        #print "within:"," ".join([str(x) for x in under])
        #print "entering:",[str(a) for a in enter]
		#print "leaving:",[str(a) for a in leave]
		# On leave restore the captured colour
        for a in leave:
            if hasattr(a,'get_color'):
                a.set_color(self.active[a])
            elif hasattr(a,'get_edgecolor'):
                a.set_edgecolor(self.active[a][0])
                a.set_facecolor(self.active[a][1])
            del self.active[a]
		# On enter, capture the color and repaint the artist
		# with the highlight colour.  Capturing colour has to
		# be done first in case the parent recolouring affects
		# the child.
        for a in enter:
            if hasattr(a,'get_color'):
                self.active[a] = a.get_color()
            elif hasattr(a,'get_edgecolor'):
                self.active[a] = [a.get_edgecolor(),a.get_facecolor()]
            else:
                self.active[a] = None
        for a in enter:
            if hasattr(a,'get_color'):
                a.set_color('white')
            elif hasattr(a,'get_edgecolor'):
                a.set_edgecolor('red')
                a.set_facecolor('white')
            else: 
                self.active[a] = None
    
        self._view_frame.canvasb.draw()	

		
		
    def on_pick(self,event):
        vf = self._view_frame
		
        bar = event.artist
		
        #print(bar.get_facecolor())	
		
		#Matrix of coords,
		
        coords = bar.get_bbox().get_points()
		
        dose = int(round(coords[1][0], 0))
        prob = coords[1][1]
		
        idx = vf.isovalue_list.InsertStringItem(sys.maxint, label = "", it_kind=1)

        if idx > 2:
            vf.isovalue_list.DeleteItem(idx)
			
            if self.radio_id == 9:
                vf.SetStatusText( "No radio button selected...")
                return
				
            id = self.radio_id
			
            isovalue = self.isoline_sliders[id].GetValue()
			
            index_old = self.dic_iso_to_index[isovalue]
            self.bars[index_old].set_facecolor('black')
						
            index_new = self.dic_iso_to_index[dose]
            self.bars[index_new].set_facecolor(self.primary_colors_float[id])
            self.active[bar][1] = self.primary_colors_float[id]
				
            self.isoline_spins[id].SetValue(dose)
            self.isoline_sliders[id].SetValue(self.isoline_spins[id].GetValue())
				
            self._view_frame.canvasb.draw()	

            self.isovalue_objs[id].set_isovalue(dose)

            self.slice_viewerA.render()
            self.slice_viewerC.render()
            self.slice_viewerS.render()				
				
            return
				
        else:
            index = self.dic_iso_to_index[dose]
            self.bars[index].set_facecolor(self.primary_colors_float[idx])
            self.active[bar][1] = self.primary_colors_float[idx]
		
        r = self.primary_colors[idx][0]
        g = self.primary_colors[idx][1]
        b = self.primary_colors[idx][2]
		
		
        isoline_slider = wx.Slider(vf.isovalue_list, idx, dose, 70, 93, wx.DefaultPosition, wx.Size( 100,-1 ), wx.SL_HORIZONTAL )
        isoline_spin = wx.SpinCtrl(vf.isovalue_list, idx, pos=(55, 90), size=(60, -1), min=70, max=93, initial = dose)  
        #color_picker = csel.ColourSelect(vf.isovalue_list, idx, "       ", wx.Colour(r,g,b)) 
        #color_picker = wx.ColourPickerCtrl(vf.isovalue_list, idx, wx.Colour(r, g, b), wx.Point(200, 400), wx.Size(20,20), wx.CLRP_DEFAULT_STYLE)
        choice = wx.ComboBox(vf.isovalue_list, idx, choices=['Contours','Median','Bands','50% band','100% band','Outliers', 'Full contour boxplot'], value = 'Contours', style = wx.CB_READONLY)
        #active = wx.CheckBox(vf.isovalue_list, idx, label='          ')
        active = wx.RadioButton(vf.isovalue_list, idx, label=' ')
			
        self.isoline_sliders[idx] = isoline_slider
        self.isoline_spins[idx] = isoline_spin
        #self.colors[idx] = color_picker	
        self.options[idx] = choice
        self.actives[idx] = active
			
        vf.isovalue_list.SetItemWindow(idx, 0, isoline_spin)
        vf.isovalue_list.SetItemWindow(idx, 1, isoline_slider)
        #vf.isovalue_list.SetItemWindow(idx, 2, color_picker)
        vf.isovalue_list.SetItemWindow(idx, 2, choice)
        vf.isovalue_list.SetItemWindow(idx, 3, active)
        vf.isovalue_list.SetItemBackgroundColour(idx, wx.Colour(r,g,b))
			
        idx_axial = self.slice_viewerA.ipws[0].GetSliceIndex()
        idx_sagittal = self.slice_viewerS.ipws[1].GetSliceIndex()
        idx_coronal = self.slice_viewerC.ipws[2].GetSliceIndex()
			
        iso_object = Isovalue(self.nr_doseplans, self.doseplans, self.xmin, self.xmax, \
							self.ymin, self.ymax, self.zmin, self.zmax, \
							self.image_data50, self.image_data100)
        iso_object.initialize_pipeline()
		
        if idx == 0:
            temp_ctf = self.ctf_yellow
        elif idx == 1:
            temp_ctf = self.ctf_red
        elif idx == 2:
            temp_ctf = self.ctf_blue
		
        for plan in range(len(self.planlist)):
            probability = self.contours_info[dose][plan][1]
            color = temp_ctf.GetColor(probability)
            opacity = self.otf.GetValue(probability)
            iso_object.setup_isoline_actors(plan,idx_axial,idx_sagittal,idx_coronal,dose, color, opacity)
			
        self.isovalue_objs.append(iso_object)		

    def _handler_introspect(self, e):
        self.miscObjectConfigure(self._view_frame, self, 'EnsembleViewer')


    def _handler_reset_all(self, e):
        self.reset_axial()
        self.reset_sagittal()
        self.reset_coronal()

    def _handler_variability_visible(self, e):
        if str(self._view_frame.check1.GetValue()) == 'None':
            self.grid_actorA.VisibilityOff()
            self.hf_actorA.VisibilityOff()
        elif str(self._view_frame.check1.GetValue()) == 'Grid':
            self.grid_actorA.VisibilityOn()
            self.hf_actorA.VisibilityOff()
        elif str(self._view_frame.check1.GetValue()) == 'Heights':
            self.grid_actorA.VisibilityOff()
            self.hf_actorA.VisibilityOn()
        elif str(self._view_frame.check1.GetValue()) == 'Both':
            self.grid_actorA.VisibilityOn()
            self.hf_actorA.VisibilityOn()
        self.render()


    def _handler_grid_visible(self, e):
        if self._view_frame.check3.IsChecked():
            self.grid_actorS.VisibilityOn()
        else:
            self.grid_actorS.VisibilityOff()


        if self._view_frame.check2.IsChecked():
            self.grid_actorC.VisibilityOn()
        else:
            self.grid_actorC.VisibilityOff()

        self.render()


    def _handler_file_open(self, event):
        """Handler for file opening
        """
        filters = 'Volume files (*.vti)|*.vti;'
        dlg = wx.FileDialog(self._view_frame, "Please choose a data volume file", self._config.last_used_dir, "", filters, wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            filename=dlg.GetFilename()
            self._config.last_used_dir=dlg.GetDirectory()
            full_file_path = "%s/%s" % (self._config.last_used_dir, filename)
            self.load_data_from_file(full_file_path)
            dlg2 = wx.FileDialog(self._view_frame, "Please choose the dose plan file(s)", self._config.last_used_dir, "", filters, wx.MULTIPLE)
            if dlg2.ShowModal() == wx.ID_OK:
                ffilelist=dlg2.GetPaths()
                self._config.last_used_dir=dlg2.GetDirectory()
                self.load_plan_from_file(ffilelist)
            dlg2.Destroy()
        dlg.Destroy()
		
    def create_csv_file(self):
		with open('heatmap.csv', 'w') as csvfile:
			fieldnames = ['Isodose', 'Doseplans', 'Probabilities']
			writer = csv.DictWriter(csvfile, fieldnames=fieldnames, lineterminator='\n') 

			writer.writeheader()
    
			for k, v in self.contours_info.items():
				for info in v:
					writer.writerow({'Isodose': k, 'Doseplans': 'DP ' + str(info[0]), 'Probabilities': info[1]})
					
					
    def create_mean_std_file(self, file):
        voxel_values = {}
        self.coordinates = []
        print("printing mean")
		
        if file == "pb_ano1.vti":
            for z, y, x in product(range(55,85), range(45,75), range(75,115)):
                if self.planlist[0].GetScalarComponentAsDouble(x, y, z, 0) <> 0 and self.planlist[1].GetScalarComponentAsDouble(x, y, z, 0) <> 0 and self.planlist[2].GetScalarComponentAsDouble(x, y, z, 0) <> 0:
                    voxels = [self.planlist[j].GetScalarComponentAsDouble(x, y, z, 0) for j in range(1, len(self.planlist))]
                    voxel_values[x, y, z] = [np.mean(voxels),np.std(voxels)]
                    self.coordinates.append([x,y,z])
                    self.meanx.append(np.mean(voxels))
                    self.stdy.append(np.std(voxels))
        else:
            for z, y, x in product(range(self.zmin,self.zmax+1), range(self.ymin,self.ymax+1), range(self.xmin,self.xmax+1)):
                if self.planlist[0].GetScalarComponentAsDouble(x, y, z, 0) <> 0 and self.planlist[1].GetScalarComponentAsDouble(x, y, z, 0) <> 0 and self.planlist[2].GetScalarComponentAsDouble(x, y, z, 0) <> 0:
                    voxels = [self.planlist[j].GetScalarComponentAsDouble(x, y, z, 0) for j in range(1, len(self.planlist))]
                    voxel_values[x, y, z] = [np.mean(voxels),np.std(voxels)]
                    self.coordinates.append([x,y,z])
                    self.meanx.append(np.mean(voxels))
                    self.stdy.append(np.std(voxels))
		
		
    def _pick_event(self, event, obj):
        self._handler_add_flags()


    def _handler_overlay(self, event):
        if self._view_frame.overbut.GetValue():
            self._view_frame.overbut.SetLabel("Regions")
            self.create_average_plan()
        else:
            self._view_frame.overbut.SetLabel("Variability")
            self.region_growing(self.lastpos, self.lastval)

			
    def _handler_default_view(self, event):
        """Event handler for when the user selects View -> Default from
        the main menu.
        """
        vf = self._view_frame
        vf._mgr.LoadPerspective(vf._perspectives['default'])

    def _handler_max_image_view(self, event):
        """Event handler for when the user selects View -> Max Image
        from the main menu.
        """
        vf = self._view_frame
        vf._mgr.LoadPerspective(vf._perspectives['max_image'])
			
    def _handler_contour_view(self,event):
        """Event handler for when the user selects View -> Contour Uncertainty view
        from the main menu.
        """
        vf = self._view_frame
        vf._mgr.LoadPerspective(vf._perspectives['contour_view'])
		
        self.scBarWidget.Off()
        self.slice_viewerA.render()
        vf.text_select1.Enable(False)
        vf.select1.Enable(False)
        vf.text_select2.Enable(False)
        vf.select2.Enable(False)
        vf.text_overlay.Enable(False)
        vf.show_overlay.Enable(False)
        vf.text_colormap.Enable(False)
        vf.radio_mean.Enable(False)
        vf.text_radio_mean.Enable(False)
        vf.radio_std.Enable(False)
        vf.text_radio_std.Enable(False)
			
    def _handler_voxel_view(self,event):
        """Event handler for when the user selects View -> Voxel Uncertainty view
        from the main menu.
        """
        vf = self._view_frame
        vf._mgr.LoadPerspective(vf._perspectives['voxel_view'])
		
        self.scBarWidget.On()
        self.slice_viewerA.render()
        vf.text_select1.Enable(True)
        vf.select1.Enable(True)
        vf.text_select2.Enable(True)
        vf.select2.Enable(True)
        vf.text_overlay.Enable(True)
        vf.show_overlay.Enable(True)
        vf.text_colormap.Enable(True)
        vf.radio_mean.Enable(True)
        vf.text_radio_mean.Enable(True)
        vf.radio_std.Enable(True)
        vf.text_radio_std.Enable(True)
			
		
    def render(self):
        """Method that calls Render() on the embedded RenderWindow.
        Use this after having made changes to the scene.
        """
        self._view_frame.render()
        #self.ren_iso.Render()
        self.slice_viewerA.render()
        self.slice_viewerC.render()
        self.slice_viewerS.render()
        #self.slice_viewerDP.render()


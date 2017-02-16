# EnsembleViewerFrame by Pedro Silva
# Description
#   Class that defines the frame used by the EnsembleViewer.
#
# Based on SkeletonAUIViewerFrame:
# Copyright (c) Charl P. Botha, TU Delft.
# All rights reserved.
# See COPYRIGHT for details.

import cStringIO
from vtk.wx.wxVTKRenderWindowInteractor import wxVTKRenderWindowInteractor

from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as NavigationToolbar
from matplotlib.figure import Figure

import wx
import wx.combo
import vtk
import os
import sys
import math
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import numpy as np
from matplotlib import colors
import matplotlib.patches as mpatches
import wx.lib.agw.ultimatelistctrl as ulc
import wx.lib.agw.floatspin as fs
import wx.lib.colourselect as csel
import wx.lib.mixins.listctrl
from wx.lib.mixins.listctrl import CheckListCtrlMixin, ListCtrlAutoWidthMixin
import wx.html
from wx.lib.wordwrap import wordwrap
import webbrowser
from mpldatacursor import datacursor

# wxPython 2.8.8.1 wx.aui bugs severely on GTK. See:
# http://trac.wxwidgets.org/ticket/9716
# Until this is fixed, use this PyAUI to which I've added a
# wx.aui compatibility layer.
if wx.Platform == "__WXGTK__":
    from external import PyAUI
    wx.aui = PyAUI
else:
    import wx.aui

class EnsembleViewerFrame(wx.Frame, wx.lib.mixins.listctrl.ColumnSorterMixin):
    """wx.Frame child class used by EnsembleViewer for its
    interface.

    This is an AUI-managed window, so we create the top-level frame,
    and then populate it with AUI panes.
    """

    def __init__(self, parent, id=-1, title="", name=""):
        """Populates the menu and adds all required panels
        """
        wx.Frame.__init__(self, parent, id=id, title=title,
                pos=wx.DefaultPosition, size=(1800,830), name=name) #1000,875

        self.menubar = wx.MenuBar()
        self.SetMenuBar(self.menubar)

        views_menu = wx.Menu()
        self.views_default_id = wx.NewId()
        views_menu.Append(self.views_default_id, "&Default\tCtrl-D",
                         "Activate default view layout.", wx.ITEM_NORMAL)

        self.views_max_image_id = wx.NewId()
        views_menu.Append(self.views_max_image_id, "&Axial-Sagittal-Coronal View\tCtrl-M",
                         "Activate maximum image view size layout.",
                         wx.ITEM_NORMAL)
		
        self.views_contour_view_id = wx.NewId()
        views_menu.Append(self.views_contour_view_id, "&Contour Uncertainty view\tCtrl-C",
                         "Activate contour uncertainty view size layout.",
                         wx.ITEM_NORMAL)

        self.views_voxel_view_id = wx.NewId()
        views_menu.Append(self.views_voxel_view_id, "&Voxel Uncertainty view\tCtrl-V",
                         "Activate voxel uncertainty view size layout.",
                         wx.ITEM_NORMAL)

        self.menubar.Append(views_menu, "&Views")
		
		
        help_menu = wx.Menu()
        help_about_id = wx.NewId()
        help_menu.Append(help_about_id, "&About\tCtrl-0",
                         "Info about application.", wx.ITEM_NORMAL)
						 
        self.menubar.Append(help_menu, "&Help")
		
        # tell FrameManager to manage this frame
        self._mgr = wx.aui.AuiManager()
        self._mgr.SetManagedWindow(self)

        self._mgr.AddPane(self._create_patients_pane(), wx.aui.AuiPaneInfo().
                          Name("patient").Caption("Patient Data").
                          Left().
                          BestSize(wx.Size(600,400)).
                          MinimizeButton(True).MaximizeButton(True))

		
        self._mgr.AddPane(self._create_controls_pane(), wx.aui.AuiPaneInfo().
                          Name("control").Caption("Dose Plan Explorer").
                          Bottom().
                          BestSize(wx.Size(600,400)).
                          MinimizeButton(True).MaximizeButton(True))
						  
        self._mgr.AddPane(self._create_axial_slices_pane(), wx.aui.AuiPaneInfo().
                          Name("axial").Caption("Axial").
                          Center().
                          BestSize(wx.Size(400,400)).
                          CloseButton(False).MaximizeButton(True))
						  
        self._mgr.AddPane(self._create_3D_pane(), wx.aui.AuiPaneInfo().
                          Name("3dview").Caption("3D Dose Plan").
                          Left().
                          BestSize(wx.Size(1000,800)).
                          MinimizeButton(True).MaximizeButton(True))

        self._mgr.AddPane(self._create_sagittal_slices_pane(), wx.aui.AuiPaneInfo().
                          Name("sagittal").Caption("Sagittal").
                          Right().
                          BestSize(wx.Size(400,400)).
                          MinimizeButton(True).MaximizeButton(True))


        self._mgr.AddPane(self._create_coronal_slices_pane(), wx.aui.AuiPaneInfo().
                          Name("coronal").Caption("Coronal").
                          Right().
                          BestSize(wx.Size(400,400)).
                          MinimizeButton(True).MaximizeButton(True))

        self._mgr.AddPane(self._create_barplot_pane(), wx.aui.AuiPaneInfo().
                          Name("overview").Caption("Probability Overview").
                          Bottom().
                          BestSize(wx.Size(1000,800)).
                          MinimizeButton(True).MaximizeButton(True))
						  
        self._mgr.AddPane(self._create_probs_pane(), wx.aui.AuiPaneInfo().
                          Name("probs").Caption("Probabilities for Dose Plans").
                          Bottom().
                          BestSize(wx.Size(1000,800)).
                          MinimizeButton(True).MaximizeButton(True))				  						  
						  
        self._mgr.AddPane(self._create_distplot_pane(), wx.aui.AuiPaneInfo().
                          Name("distplot").Caption("Exploration of dose distribution").
                          Bottom().
                          BestSize(wx.Size(1000,800)).
                          MinimizeButton(True).MaximizeButton(True))
						  
        self._mgr.AddPane(self._create_scatterplot_pane(), wx.aui.AuiPaneInfo().
                          Name("scatterplot").Caption("Variability scatterplot").
                          Bottom().
                          BestSize(wx.Size(1000,800)).
                          MinimizeButton(True).MaximizeButton(True))
		

        self.SetMinSize(wx.Size(400, 300))

        # first we save this default perspective with all panes
        # visible
        self._perspectives = {}
        self._mgr.GetPane("doseplan").Hide()
        self._mgr.GetPane("scatterplot").Hide()
        self._mgr.GetPane("3dview").Hide()
        self._mgr.GetPane("distplot").Hide()
        self._perspectives['default'] = self._mgr.SavePerspective()

        #------------- Show maximum image view ------------------#
		
		#Show axial,coronal and sagittal panes
        self._mgr.GetPane("axial").Show()
        self._mgr.GetPane("coronal").Show()
        self._mgr.GetPane("sagittal").Show()

		#Hide all the others		
        self._mgr.GetPane("patient").Hide()		
        self._mgr.GetPane("control").Hide()
        self._mgr.GetPane("overview").Hide()
        self._mgr.GetPane("probs").Hide()
        self._mgr.GetPane("3dview").Hide()
        self._mgr.GetPane("scatterplot").Hide()
        self._mgr.GetPane("distplot").Hide()
        # save the perspective again
        self._perspectives['max_image'] = self._mgr.SavePerspective()

        #------------- Show contour uncertainty view ------------------#
		
		#Show axial, coronal, sagittal, control, overview and probabilities panes
        self._mgr.GetPane("axial").Show()
        self._mgr.GetPane("coronal").Right()
        self._mgr.GetPane("coronal").Show()
        self._mgr.GetPane("sagittal").Right()
        self._mgr.GetPane("sagittal").Show()
        self._mgr.GetPane("control").Show()
        self._mgr.GetPane("overview").Show()
        self._mgr.GetPane("probs").Show()
		
		#Hide all the others
        self._mgr.GetPane("patient").Hide()
        self._mgr.GetPane("3dview").Hide()
        self._mgr.GetPane("scatterplot").Hide()
        self._mgr.GetPane("distplot").Hide()
		
        self._perspectives['contour_view'] = self._mgr.SavePerspective()
		
        #------------- Show voxel uncertainty view ------------------#		
		
		#Show 3dview, scatterplot, axial and distplot panes
        self._mgr.GetPane("axial").Left().Center()
        self._mgr.GetPane("axial").Show()
        self._mgr.GetPane("3dview").Left().Center()
        self._mgr.GetPane("3dview").Show()
        self._mgr.GetPane("distplot").Right()
        self._mgr.GetPane("distplot").Show()
        self._mgr.GetPane("scatterplot").Right()
        self._mgr.GetPane("scatterplot").Show()
		
        self._mgr.GetPane("patient").Hide()
        self._mgr.GetPane("control").Hide()
        self._mgr.GetPane("coronal").Hide()
        self._mgr.GetPane("sagittal").Hide()
        self._mgr.GetPane("probs").Hide()
        self._mgr.GetPane("overview").Hide()
		
        self._perspectives['voxel_view'] = self._mgr.SavePerspective()
		
        # and put back the default perspective / view
        self._mgr.LoadPerspective(self._perspectives['default'])

        # finally tell the AUI manager to do everything that we've
        # asked
        self._mgr.Update()
		
		#Bind the events
        self.Bind(wx.EVT_MENU, self.onAbout, id = help_about_id)
	
        self.patients = {}
        self.contours = {}
		
        #sns.plt.close(self.figure)
						
        self.CreateStatusBar()
        self.SetStatusText("Status information can be find here...")
		
        self.new_pat = None
        self.aboutbox = None
		
        self.tracer = vtk.vtkImageTracerWidget()
        self.tracer.SetCaptureRadius(10.5)
        self.tracer.GetGlyphSource().SetColor(1, 0, 0)
        self.tracer.GetGlyphSource().SetScale(1.0) # set the size of the glyph handle
		
        # Set the initial rotation of the glyph if desired.  The default glyph
        # set internally by the widget is a '+' so rotating 45 deg. gives a 'x'
        self.tracer.GetGlyphSource().SetRotationAngle(90.0)
        self.tracer.GetGlyphSource().Modified()
        self.tracer.GetLineProperty().SetColor(1,0,0)
        self.tracer.SetPriority(1)
        self.tracer.AutoCloseOn()
        self.tracer.IsClosed()
		
        self.dc = None
        self.cursor_dist = None
		
    def close(self):
        """Selfdestruct :)
        """
        self.Destroy()


    def _create_patients_pane(self):
		
        panel = wx.Panel(self, -1,(-1,500))
        bSizer = wx.BoxSizer( wx.VERTICAL )
		
		#--------------------------------- Code for patient controls ---------------------------------
		
        self.toolbar = wx.ToolBar(panel, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TB_HORIZONTAL )
        self.new_patient = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('icons/addpatient.png'), shortHelp = 'Add new patient data' )
        self.load_patient = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('icons/folderOpen.png'), shortHelp = 'Load patient data')
        self.save = self.toolbar.AddLabelTool(wx.ID_ANY, '', wx.Bitmap('icons/save.png'), shortHelp = 'Save current state')
        self.toolbar.Realize() 
        
        self.toolbar.Bind(wx.EVT_TOOL, self.onNewPatient, self.new_patient) 
		
		
        bSizer.Add(self.toolbar, 0, wx.EXPAND, 5)
        

        self.patient_list = ulc.UltimateListCtrl(panel, agwStyle=wx.LC_REPORT | wx.BORDER_DEFAULT
                                         | wx.LC_SINGLE_SEL       
                                         | wx.LC_EDIT_LABELS
                                         | wx.LC_VRULES 
                                         | wx.LC_HRULES
                                         | ulc.ULC_HAS_VARIABLE_ROW_HEIGHT, size = ( -1,100 ))
        
        self.patient_list.InsertColumn(0, 'Data ID', format= ulc.ULC_FORMAT_CENTER, width = 125)
        self.patient_list.InsertColumn(1, 'Volume Data', format= ulc.ULC_FORMAT_CENTER, width = 125)
        self.patient_list.InsertColumn(2, 'Number of Plans', format= ulc.ULC_FORMAT_CENTER, width = 125)
        
        font_columns = wx.Font(10, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        
        self.patient_list.SetFont(font_columns)
		
        bSizer.Add( self.patient_list, 1, wx.ALL|wx.EXPAND, 5 )
        
        self.static_line = wx.StaticLine(panel, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.LI_HORIZONTAL )
        bSizer.Add( self.static_line, 0, wx.EXPAND |wx.ALL, 5 )
		
        panel.SetSizer(bSizer)
        bSizer.Fit(panel)
		
        return panel
		
		
		
    def _create_controls_pane(self):
		
        panel = wx.Panel(self, -1,(-1,500))
        bSizer = wx.BoxSizer( wx.VERTICAL )
		
        self.isovalue_list = ulc.UltimateListCtrl(panel, agwStyle=wx.LC_REPORT | ulc.ULC_HAS_VARIABLE_ROW_HEIGHT)
		
        '''| wx.BORDER_DEFAULT | wx.LC_SINGLE_SEL | wx.LC_EDIT_LABELS | wx.LC_VRULES | wx.LC_HRULES'''
        
        self.isovalue_list.InsertColumn(0, 'Visibility',format= ulc.ULC_FORMAT_CENTER, width = 90)
        self.isovalue_list.InsertColumn(1, 'IsoDose (Gy)',format= ulc.ULC_FORMAT_CENTER, width = 105)
        self.isovalue_list.InsertColumn(2, 'Visualize',format= ulc.ULC_FORMAT_CENTER, width = 130)
        self.isovalue_list.InsertColumn(3, 'Active',format= ulc.ULC_FORMAT_CENTER, width = 50)
		
        bSizer.Add( self.isovalue_list, 1, wx.ALL|wx.EXPAND, 5 )
		
        self.static_line2 = wx.StaticLine(panel, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.LI_HORIZONTAL )
        bSizer.Add( self.static_line2, 0, wx.EXPAND |wx.ALL, 5 )
        
        panel.SetSizer(bSizer)
        bSizer.Fit(panel)
		
        return panel

    def _create_axial_slices_pane(self):
       """Create a panel
        """
       panel = wx.Panel(self, -1)

       self.axial = wxVTKRenderWindowInteractor(panel, -1, (600,800))
	   
       self.slices_sliderA = wx.Slider(panel, -1, 11, 0, 30, wx.DefaultPosition, wx.Size( 100,-1 ), wx.SL_HORIZONTAL)
       self.slices_spinA = wx.SpinCtrl(panel, wx.ID_ANY, str(self.slices_sliderA.GetValue()), wx.DefaultPosition, wx.Size( 70,-1 ), wx.SP_ARROW_KEYS, 0, 100, 11) 
       self.slices_resetA = wx.Button(panel, -1, "Reset Cameras")
       self.text_select1 = wx.StaticText(panel, -1, "Select voxel   " , wx.Point(0, 0))
       self.select1 = wx.RadioButton(panel, wx.ID_ANY, label=' ')
       self.text_select2 = wx.StaticText(panel, -1, "Select region  " , wx.Point(0, 0))
       self.select2 = wx.RadioButton(panel, wx.ID_ANY, label=' ')
	   
       self.text_overlay = wx.StaticText(panel, -1, "Show colormap " , wx.Point(0, 0))
       self.show_overlay = wx.CheckBox(panel, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )	   
       self.show_overlay.SetValue(False)
	   
       self.text_colormap = wx.StaticText(panel, -1, "Mean " , wx.Point(0, 0))
       self.radio_mean = wx.RadioButton(panel, wx.ID_ANY, label=' ', style=wx.RB_GROUP)
       self.text_radio_mean = wx.StaticText(panel, -1, "STD  " , wx.Point(0, 0))
       self.radio_std = wx.RadioButton(panel, wx.ID_ANY, label=' ')
	   
       button_sizer = wx.BoxSizer(wx.HORIZONTAL)
       button_sizer.AddSpacer(30)
       button_sizer.Add(self.slices_sliderA)
       button_sizer.Add(self.slices_spinA)
       button_sizer.AddSpacer(30)
       button_sizer.Add(self.slices_resetA)
       button_sizer.AddSpacer(30)
       button_sizer.Add(self.text_select1)
       button_sizer.Add(self.select1)
       button_sizer.Add(self.text_select2)
       button_sizer.Add(self.select2)
       button_sizer.Add(self.text_overlay)
       button_sizer.AddSpacer(10)
       button_sizer.Add(self.show_overlay)
       button_sizer.AddSpacer(15)
       button_sizer.Add(self.text_colormap)
       button_sizer.Add(self.radio_mean)
       button_sizer.Add(self.text_radio_mean)
       button_sizer.Add(self.radio_std)
	   
       button_sizer.AddSpacer(30)
	   
       tl_sizer = wx.BoxSizer(wx.VERTICAL)
       tl_sizer.Add(self.axial, 1, wx.EXPAND|wx.BOTTOM, 7)
       tl_sizer.Add(button_sizer)

       panel.SetSizer(tl_sizer)
       tl_sizer.Fit(panel)

       return panel


    def _create_coronal_slices_pane(self):
       """Create a panel
       """
       panel = wx.Panel(self, -1)

       self.coronal = wxVTKRenderWindowInteractor(panel, -1, (600,800))

       self.slices_sliderC = wx.Slider(panel, -1, 128, 0, 255, wx.DefaultPosition, wx.Size( 100,-1 ), wx.SL_HORIZONTAL)
       self.slices_spinC = wx.SpinCtrl(panel, wx.ID_ANY, str(self.slices_sliderC.GetValue()), wx.DefaultPosition, wx.Size( 70,-1 ), wx.SP_ARROW_KEYS, 0, 255, 128) 
       self.slices_resetC = wx.Button(panel, -1, "Reset Camera")
	   
       button_sizer = wx.BoxSizer(wx.HORIZONTAL)
       button_sizer.AddSpacer(30)
       button_sizer.Add(self.slices_sliderC)
       button_sizer.Add(self.slices_spinC)
       button_sizer.AddSpacer(30)
       button_sizer.Add(self.slices_resetC)

       tl_sizer = wx.BoxSizer(wx.VERTICAL)
       tl_sizer.Add(self.coronal, 1, wx.EXPAND|wx.BOTTOM, 7)
       tl_sizer.Add(button_sizer)

       panel.SetSizer(tl_sizer)
       tl_sizer.Fit(panel)

       return panel



    def _create_sagittal_slices_pane(self):
       """Create a panel
       """
       panel = wx.Panel(self, -1)

       self.sagittal = wxVTKRenderWindowInteractor(panel, -1, (600,800))
	   
       self.slices_sliderS = wx.Slider(panel, -1, 128, 0, 255, wx.DefaultPosition, wx.Size( 100,-1 ), wx.SL_HORIZONTAL)
       self.slices_spinS = wx.SpinCtrl(panel, wx.ID_ANY, str(self.slices_sliderS.GetValue()), wx.DefaultPosition, wx.Size( 70,-1 ), wx.SP_ARROW_KEYS, 0, 255, 128) 
       self.slices_resetS = wx.Button(panel, -1, "Reset Camera")
	   
       button_sizer = wx.BoxSizer(wx.HORIZONTAL)
       button_sizer.AddSpacer(30)
       button_sizer.Add(self.slices_sliderS)
       button_sizer.Add(self.slices_spinS)
       button_sizer.AddSpacer(30)
       button_sizer.Add(self.slices_resetS)

       tl_sizer = wx.BoxSizer(wx.VERTICAL)
       tl_sizer.Add(self.sagittal, 1, wx.EXPAND|wx.BOTTOM, 7)
       tl_sizer.Add(button_sizer)

       panel.SetSizer(tl_sizer)
       tl_sizer.Fit(panel)

       return panel

    def _create_barplot_pane(self):
        """Create barplot for visualizing uncertainty vs isovalues
        """
        
        panel = wx.Panel(self, -1)
		
        self.figb = Figure()
        self.axb = self.figb.add_subplot(111)
		
        self.axb.set_xlabel("Isodoses", fontsize=14, fontweight = 'semibold') #fontsize=24
        self.axb.set_ylabel("Probability", fontsize = 14, fontweight = 'semibold')
        self.axb.set_xlim(68, 93)
        self.axb.set_ylim(0, 1)
		
        self.canvasb = FigureCanvas(panel, -1, self.figb)
        self.toolbarb = NavigationToolbar(self.canvasb)
		
        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.canvasb, 1, wx.EXPAND|wx.BOTTOM, 7)
        vbox.Add(self.toolbarb, 0, wx.EXPAND)
		
        panel.SetSizer(vbox)
        vbox.Fit(panel)
		
        return panel
		
    def _create_scatterplot_pane(self):
        """Create scatterplot for visualizing mean vs std deviation
        """
        panel = wx.Panel(self, -1)
		
        self.fig_scatter = Figure()
        self.ax_scatter = self.fig_scatter.add_subplot(111)
		
        families = ['serif', 'sans-serif', 'cursive', 'fantasy', 'monospace']
		
        self.ax_scatter.set_xlabel("Mean") #fontsize = 14, fontweight = 'semibold', name = families[2]
        self.ax_scatter.set_ylabel("Standard Deviation")
        #self.ax_scatter.grid(color='black', alpha=0.5, linestyle='-', linewidth=1.0)
        self.ax_scatter.set_axis_bgcolor((0.8,0.8,0.8))
        #self.ax_scatter.set_ylim(0, 35)
        #self.ax_scatter.set_ylim(0, 90)
		
        self.canvas_scatter = FigureCanvas(panel, -1, self.fig_scatter)
        self.toolbar_scatter = NavigationToolbar(self.canvas_scatter)
		
        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.canvas_scatter, 1, wx.EXPAND|wx.BOTTOM, 7)
        vbox.Add(self.toolbar_scatter, 0, wx.EXPAND)
		
        panel.SetSizer(vbox)
        vbox.Fit(panel)
		
        return panel
		
		
    def _create_distplot_pane(self):
        """Create a KDE plot for visualizing the distributions per voxel
        """
        panel = wx.Panel(self, -1)
		
        self.fig_violin = Figure()
        self.ax_violin = self.fig_violin.add_subplot(111)
		
        self.ax_violin.set_xlabel("Voxel values")
        self.ax_violin.set_ylabel("Density")
        self.ax_violin.set_xlim(60, 120)
        self.ax_violin.set_ylim(0, 0.3)
		
        self.canvas_violin = FigureCanvas(panel, -1, self.fig_violin)
        self.toolbar_violin = NavigationToolbar(self.canvas_violin)
		
        self.canvas_violin.mpl_connect('pick_event', self.onPickdist)
		
        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.canvas_violin, 1, wx.EXPAND|wx.BOTTOM, 7)
        vbox.Add(self.toolbar_violin, 0, wx.EXPAND)
		
        panel.SetSizer(vbox)
        vbox.Fit(panel)
		
        return panel
		
		
    def _create_3D_pane(self):
        """Create a panel for 3D visualization"""
		
        panel = wx.Panel(self,-1)
        self.interactor3d = wxVTKRenderWindowInteractor(panel, -1, (600,800))
        self.generate_button = wx.Button(panel, label="Generate 3D view")
        self.text_position = wx.StaticText(panel, -1, "Dose (Gy) " , wx.Point(0, 0))
        self.slider_dose3d = wx.Slider(panel, -1, 75, 60, 100, wx.DefaultPosition, wx.Size( 100,-1 ), wx.SL_HORIZONTAL)
        self.spin_dose3d = wx.SpinCtrl(panel, wx.ID_ANY, str(self.slider_dose3d.GetValue()), wx.DefaultPosition, wx.Size( 70,-1 ), wx.SP_ARROW_KEYS, min=0, max=100, initial=11)	
		
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddSpacer(30)
        button_sizer.Add(self.generate_button)
        button_sizer.AddSpacer(30)
        button_sizer.Add(self.text_position)
        button_sizer.Add(self.slider_dose3d)
        button_sizer.Add(self.spin_dose3d)
		
        listsizer = wx.BoxSizer(wx.VERTICAL)
        listsizer.Add(self.interactor3d, 1, wx.EXPAND|wx.BOTTOM, 7)
        listsizer.Add(button_sizer)
        panel.SetSizer(listsizer)
        listsizer.Fit(panel)
		
        self._create_orientation_widget(self.interactor3d)
        return panel

    def _create_orientation_widget(self, view3d):
        """setup orientation widget stuff, the axes in the bottom"""
        view3d._orientation_widget = vtk.vtkOrientationMarkerWidget()
                
        view3d._axes_actor = vtk.vtkAxesActor()
        view3d._orientation_widget.SetOrientationMarker(view3d._axes_actor)
        view3d._orientation_widget.SetInteractor(view3d)
		
    def _create_probs_pane(self):

        self.panel_heatmap = wx.Panel(self, -1)
        self.figh = Figure(facecolor=(0.941, 0.941, 0.941))
		
        self.axh = self.figh.add_subplot(111)
        self.axh.set_ylabel("DosePlans", fontsize=14) #size = 20 or 14
        self.axh.set_xlabel("Isovalues", fontsize=14) #size = 20 or 14
		
        self.canvash = FigureCanvas(self.panel_heatmap, -1, self.figh)
		
        #self.canvash.mpl_connect('pick_event', self.onPick)
        self.canvash.mpl_connect('motion_notify_event', self.onMotion)
		
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.canvash, 1, wx.EXPAND|wx.BOTTOM, 7)
        self.panel_heatmap.SetSizer(sizer)
        sizer.Fit(self.panel_heatmap)
		
        return self.panel_heatmap

	#Decorator function to guarantee that the datacursor only runs once!
    def run_once(f):
        def wrapper(*args, **kwargs):
            if not wrapper.has_run:
                wrapper.has_run = True
                return f(*args, **kwargs)
        wrapper.has_run = False
        return wrapper


    @run_once
    def onPick(self,event):
		#The datacursor works only on points of the mesh...
        self.dc = datacursor(hover=True, axes = self.axh, keybindings=dict(hide='h', toggle='e'), formatter = lambda **d: "Isovalue: {:.0f}\nDosePlan: {:.0f}\nProbability: {:.4f}".format(d["x"] + 70,self.nrdp - (d["y"]+1),d["z"]))  

    @run_once
    def onPickdist(self,event):
        self.cursor_dist = datacursor(hover=True, axes = self.ax_violin, keybindings=dict(hide='h', toggle='e'), display = "single")
			
    def onMotion(self,event):
        if not event.inaxes: 
            return
	
        xint = int(event.xdata) #isovalue
        yint = int(event.ydata) #doseplan
		
        self.rect = mpatches.Rectangle((xint, yint),1,1,fill=False, edgecolor="#00FFFF",linewidth=2.5)
        self.axh.add_patch(self.rect)
        self.canvash.draw()
        self.rect.remove()		
		
    def onNewPatient(self, event):
        if not self.new_pat:
            self.new_pat = NewPatientFrame(self)
            self.new_pat.Show()
			
    def onAbout(self,event):
        if not self.aboutbox:
            self.aboutbox = AboutDlg(self)
            self.aboutbox.Show()
		
    def render(self):
        """Update embedded RWI, i.e. update the image.
        """
        self.axial.Render()
        self.coronal.Render()
        self.sagittal.Render()
        #self.isosurface.Render()
        #self.rwi_pcp.Render()

    def _handler_default_view(self, event):
        """Event handler for when the user selects View -> Default from
        the main menu.
        """
        self._mgr.LoadPerspective(
            self._perspectives['default'])

    def _handler_max_image_view(self, event):
        """Event handler for when the user selects View -> Max Image
        from the main menu.
        """
        self._mgr.LoadPerspective(
            self._perspectives['max_image'])
			
    def _handler_control_view(self,event):
        """Event handler for when the user selects View -> Dose Plan Explorer
        from the main menu.
        """
        self._mgr.LoadPerspective(
			self._perspectives['control_view'])
			
    def _handler_voxel_view(self,event):
        """Event handler for when the user selects View -> Voxel Uncertainty view
        from the main menu.
        """
        self._mgr.LoadPerspective(
			self._perspectives['voxel_view'])
			
    def add_newpatient(self, pat_nr, pat_info, nr_doseplans):
        self.pn = pat_nr
        self.pi = pat_info
        self.nr = nr_doseplans
        
        if self.patients.has_key(self.pn):
            dial = wx.MessageDialog(None, 'That patient already exists!', 'Already existent patient', wx.OK | wx.ICON_EXCLAMATION)
            dial.ShowModal()
        else:
            self.patients.update({self.pn : self.pi})
            idx = self.patient_list.InsertStringItem(sys.maxint, str(self.pn)) #Insert patient number
            self.patient_list.SetStringItem(idx, 1, os.path.split(self.pi[0])[1]) #Insert name of volume file
            self.patient_list.SetStringItem(idx, 2, str(self.nr)) #Insert number of dose plans
	
class NewPatientFrame ( wx.Frame ):
    
    def __init__( self, main_frame ):
        wx.Frame.__init__ ( self, None, id = wx.ID_ANY, title = u"Add new patient", pos = wx.DefaultPosition, size = wx.Size( 500,222 ), style = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL )
        self.main_frame = main_frame
		
        #self.patientinfo = []
        
        self.SetSizeHintsSz( wx.DefaultSize, wx.DefaultSize )
        
        sizer_frame = wx.BoxSizer( wx.VERTICAL )
        
        self.panel = wx.Panel( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
        sizer_panel = wx.BoxSizer( wx.VERTICAL )
        
        sizer_info = wx.FlexGridSizer( 0, 3, 0, 0 )
        sizer_info.SetFlexibleDirection( wx.BOTH )
        sizer_info.SetNonFlexibleGrowMode( wx.FLEX_GROWMODE_SPECIFIED )
        
        self.patient_label = wx.StaticText( self.panel, wx.ID_ANY, u"Data ID:", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.patient_label.Wrap( -1 )
        self.patient_label.SetFont( wx.Font( 12, 74, 90, 92, False, "Calibri" ) )
        
        sizer_info.Add( self.patient_label, 0, wx.ALL, 5 )
        
        self.patient_data = wx.TextCtrl( self.panel, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )
        sizer_info.Add( self.patient_data, 0, wx.ALL, 5 )
        
        self.m_staticText5 = wx.StaticText( self.panel, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )
        self.m_staticText5.Wrap( -1 )
        sizer_info.Add( self.m_staticText5, 0, wx.ALL, 5 )
        
        self.volume_label = wx.StaticText( self.panel, wx.ID_ANY, u"Volume Data:", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.volume_label.Wrap( -1 )
        self.volume_label.SetFont( wx.Font( 12, 74, 90, 92, False, "Calibri" ) )
        
        sizer_info.Add( self.volume_label, 0, wx.ALL, 5 )
        
        self.volume_data = wx.TextCtrl( self.panel, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )
        sizer_info.Add( self.volume_data, 0, wx.ALL, 5 )
        
        self.load_volume = wx.Button( self.panel, wx.ID_ANY, u"Load volume data", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.load_volume.Bind(wx.EVT_BUTTON, self._handler_open_volume)
        
        sizer_info.Add( self.load_volume, 0, wx.ALL, 5 )
        
        self.plans_label = wx.StaticText( self.panel, wx.ID_ANY, u"Dose Plans:", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.plans_label.Wrap( -1 )
        self.plans_label.SetFont( wx.Font( 12, 74, 90, 92, False, "Calibri" ) )
        
        sizer_info.Add( self.plans_label, 0, wx.ALL, 5 )
        
        self.plans_data = wx.TextCtrl( self.panel, wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, 0 )
        sizer_info.Add( self.plans_data, 0, wx.ALL, 5 )
        
        self.load_plans = wx.Button( self.panel, wx.ID_ANY, u"Load dose plans data", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.load_plans.Bind(wx.EVT_BUTTON, self._handler_open_plans)
        
        sizer_info.Add( self.load_plans, 0, wx.ALL, 5 )
        
        sizer_panel.Add( sizer_info, 1, wx.EXPAND, 5 )
        
        self.m_staticline1 = wx.StaticLine(self.panel, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.LI_HORIZONTAL )
        sizer_panel.Add( self.m_staticline1, 0, wx.EXPAND |wx.ALL, 5 )
        
        sizer_buttons = wx.BoxSizer( wx.HORIZONTAL )
        
        self.add_patient = wx.Button(self.panel, wx.ID_ANY, u"&Add Patient", wx.DefaultPosition, wx.DefaultSize, 0 )
        self.add_patient.Bind(wx.EVT_BUTTON, self.load_info)
        
        sizer_buttons.Add( self.add_patient, 0, wx.ALL, 5 )
        
        self.cancel = wx.Button( self.panel, wx.ID_ANY, u"&Cancel", wx.DefaultPosition, wx.DefaultSize, 0 )
        sizer_buttons.Add( self.cancel, 0, wx.ALL, 5 )
        
        self.cancel.Bind(wx.EVT_BUTTON, self.onClose)
        
        sizer_panel.Add( sizer_buttons, 0, wx.ALIGN_RIGHT, 5 )
        
        
        self.panel.SetSizer( sizer_panel )
        self.panel.Layout()
        sizer_panel.Fit( self.panel )
        sizer_frame.Add( self.panel, 1, wx.EXPAND, 5 )
        
        
        self.SetSizer( sizer_frame )
        self.Layout()
        
        self.Centre( wx.BOTH )
        
    def _handler_open_volume(self, event):
        """Handler for file opening
        """
        if not self.volume_data.IsEmpty():
            self.volume_data.Remove(0,100)
        filters = 'Volume files (*.vti)|*.vti;'
        dlg = wx.FileDialog(self, "Please choose a data volume file", "", "", filters, wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.volume_path = dlg.GetPath()
            filename=dlg.GetFilename()
            self.volume_data.AppendText(filename)
        dlg.Destroy()
        
            
    def _handler_open_plans(self, event):
        """Handler for file opening
        """
        if not self.plans_data.IsEmpty():
            self.plans_data.Remove(0,100)
        filters = 'Volume files (*.vti)|*.vti;'
        dlg2 = wx.FileDialog(self, "Please choose the dose plan file(s)", "", "", filters, wx.MULTIPLE)
        if dlg2.ShowModal() == wx.ID_OK:
            self.doseplan_path = dlg2.GetPaths()
            for filepath in dlg2.GetPaths():
                filename = os.path.split(filepath)[1]
                self.plans_data.AppendText(filename)
                self.plans_data.AppendText(',')
            
        dlg2.Destroy()
    
    def load_info(self,event):
        if self.patient_data.IsEmpty() or self.volume_data.IsEmpty() or self.plans_data.IsEmpty():
            dial = wx.MessageDialog(None, 'Please fill ALL the relevant fields!', 'Incomplete fields', wx.OK | wx.ICON_EXCLAMATION)
            dial.ShowModal()
        else:
            self.patientinfo = []
            self.patientnumber = int(self.patient_data.GetValue())
            self.patientinfo.append(self.volume_path)
            self.patientinfo.append(self.doseplan_path)
            self.nr_doseplans = len(self.doseplan_path)
            self.main_frame.add_newpatient(self.patientnumber, self.patientinfo, self.nr_doseplans)
                
            
    def onClose(self, event):
        """"""
        self.Close()
	


class AboutDlg(wx.Frame):
 
    def __init__(self, parent):
 
        wx.Frame.__init__(self, None, wx.ID_ANY, title="About", size=(400,400))
 
        html = wxHTML(self)
 
        html.SetPage(
            ''
 
            "<h2> Ensemble Viewer (1.0.0)</h2>"
 
            "<p> Module to visualize variability among ensemble dose plans from MRI images of the prostate. "
 
            "For the project Uncertainty Visualization in Radiotherapy Dose Planning, developed by Pedro Silva. </p>"
			
            "<p> 2016 TU Eindhoven </p>"
 
            "<p><b>For more information:</h3></p>"
 
            '<p><b><a href="https://www.tue.nl/en/university/departments/biomedical-engineering/research/research-groups/medical-image-analysis/organization/group-members/master-students/pedro-silva/">About the developer</a></b></p>'
 
            '<p><b><a href="http://www.wxpython.org">wxPython 2.8</a></b></p>'
            )

class wxHTML(wx.html.HtmlWindow):
     def OnLinkClicked(self, link):
         webbrowser.open(link.GetHref())
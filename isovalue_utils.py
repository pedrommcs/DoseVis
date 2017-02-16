# Copyright (c) Pedro Silva, TU Eindhoven.
# All rights reserved.
# See COPYRIGHT for details.
# ---------------------------------------

import operator
import vtk
import wx

class Isovalue:
    """Class to define the set of contours associated with the isovalues.
	
	Attributes:
	
		- nr_doseplans: an integer representing the number of dose plans in the ensemble.
		- doseplans: a dictionary representing the dose plans in the ensemble (VTI data) 
			{DP1: VTIdata, DP2: VTIdata, (...), DPn: VTIdata}
	
	
	"""

    def __init__(self, nr_doseplans, doseplans, xmin, xmax, ymin, ymax, zmin, zmax, band50, band100):
	
        self.nr_doseplans = nr_doseplans
        self.doseplans = doseplans

        self.extracts_axial = {}
        self.contours_axial = {}
        self.contour_mappers_axial = {}		
        self.contour_actors_axial = {}
		
        self.extracts_coronal = {}
        self.contours_coronal = {}
        self.contour_mappers_coronal = {}		
        self.contour_actors_coronal = {}
		
        self.extracts_sagittal = {}
        self.contours_sagittal = {}
        self.contour_mappers_sagittal = {}		
        self.contour_actors_sagittal = {}
		
        self.xmin = xmin
        self.xmax = xmax
        self.ymin = ymin
        self.ymax = ymax
        self.zmin = zmin
        self.zmax = zmax
		
        self.band50 = band50
        self.band100 = band100
		
		
    def initialize_pipeline(self):
		
        """ Set up the necessary VTK classes for the pipeline, and the color of the contours"""
		
        for i in range(self.nr_doseplans):
            self.extracts_axial["c{0}".format(i)] = vtk.vtkExtractVOI()
            self.contours_axial["c{0}".format(i)] = vtk.vtkContourFilter()
            self.contour_mappers_axial["c{0}".format(i)] = vtk.vtkPolyDataMapper()
            self.contour_actors_axial["c{0}".format(i)] = vtk.vtkActor()
            self.contour_actors_axial["c{0}".format(i)].GetProperty().SetColor(0,1,0)
            self.contour_actors_axial["c{0}".format(i)].GetProperty().SetLineWidth(2)
			
            self.extracts_sagittal["c{0}".format(i)] = vtk.vtkExtractVOI()
            self.contours_sagittal["c{0}".format(i)] = vtk.vtkContourFilter()
            self.contour_mappers_sagittal["c{0}".format(i)] = vtk.vtkPolyDataMapper()
            self.contour_actors_sagittal["c{0}".format(i)] = vtk.vtkActor()
            self.contour_actors_sagittal["c{0}".format(i)].GetProperty().SetColor(0,1,0)
            self.contour_actors_sagittal["c{0}".format(i)].GetProperty().SetLineWidth(2)
			
            self.extracts_coronal["c{0}".format(i)] = vtk.vtkExtractVOI()
            self.contours_coronal["c{0}".format(i)] = vtk.vtkContourFilter()
            self.contour_mappers_coronal["c{0}".format(i)] = vtk.vtkPolyDataMapper()
            self.contour_actors_coronal["c{0}".format(i)] = vtk.vtkActor()
            self.contour_actors_coronal["c{0}".format(i)].GetProperty().SetColor(0,1,0)
            self.contour_actors_coronal["c{0}".format(i)].GetProperty().SetLineWidth(2)
			
            self.extracts_axial["c{0}".format(i)].SetInput(self.doseplans["p{0}".format(i)])
            self.extracts_coronal["c{0}".format(i)].SetInput(self.doseplans["p{0}".format(i)])
            self.extracts_sagittal["c{0}".format(i)].SetInput(self.doseplans["p{0}".format(i)])
			
			
    def setup_isoline_actors(self, plan, sliceA_index,sliceS_index,sliceC_index, isoline_slider, color, opacity):
        
		
		#----- Set the actors according to the current slice ----#
		
		# ------------------------------ Axial Setup -----------------------------------
        self.extracts_axial["c{0}".format(plan)].SetVOI(self.xmin, self.xmax, \
					   self.ymin, self.ymax, \
					   sliceA_index, sliceA_index)
        self.extracts_axial["c{0}".format(plan)].SetSampleRate(1, 1, 1)
		
        self.contours_axial["c{0}".format(plan)].SetInput(self.extracts_axial["c{0}".format(plan)].GetOutput())
        self.contours_axial["c{0}".format(plan)].SetValue(0,float(isoline_slider))
			
        self.contour_mappers_axial["c{0}".format(plan)].SetInputConnection(self.contours_axial["c{0}".format(plan)].GetOutputPort())
        self.contour_mappers_axial["c{0}".format(plan)].ScalarVisibilityOff()
			
        self.contour_actors_axial["c{0}".format(plan)].SetMapper(self.contour_mappers_axial["c{0}".format(plan)])

        self.contour_actors_axial["c{0}".format(plan)].GetProperty().SetColor(color)
        self.contour_actors_axial["c{0}".format(plan)].GetProperty().SetOpacity(opacity)
		
		
		#-------------------------------- Sagittal Setup -------------------------------------
		
        self.extracts_sagittal["c{0}".format(plan)].SetVOI(sliceS_index, sliceS_index, \
					   self.ymin, self.ymax, \
					   self.zmin, self.zmax)
        self.extracts_sagittal["c{0}".format(plan)].SetSampleRate(1, 1, 1)
		
        self.contours_sagittal["c{0}".format(plan)].SetInput(self.extracts_sagittal["c{0}".format(plan)].GetOutput())
        self.contours_sagittal["c{0}".format(plan)].SetValue(0,float(isoline_slider))
			
        self.contour_mappers_sagittal["c{0}".format(plan)].SetInputConnection(self.contours_sagittal["c{0}".format(plan)].GetOutputPort())
        self.contour_mappers_sagittal["c{0}".format(plan)].ScalarVisibilityOff()
			
        self.contour_actors_sagittal["c{0}".format(plan)].SetMapper(self.contour_mappers_sagittal["c{0}".format(plan)])
        self.contour_actors_sagittal["c{0}".format(plan)].GetProperty().SetColor(color)
        self.contour_actors_sagittal["c{0}".format(plan)].GetProperty().SetOpacity(opacity)
		
		# -------------------------------- Coronal Setup -------------------------------------
		
        self.extracts_coronal["c{0}".format(plan)].SetVOI(self.xmin, self.xmax, \
					   sliceC_index, sliceC_index, \
					   self.zmin, self.zmax)
        self.extracts_coronal["c{0}".format(plan)].SetSampleRate(1, 1, 1)
		
        self.contours_coronal["c{0}".format(plan)].SetInput(self.extracts_coronal["c{0}".format(plan)].GetOutput())
        self.contours_coronal["c{0}".format(plan)].SetValue(0,float(isoline_slider))
			
        self.contour_mappers_coronal["c{0}".format(plan)].SetInputConnection(self.contours_coronal["c{0}".format(plan)].GetOutputPort())
        self.contour_mappers_coronal["c{0}".format(plan)].ScalarVisibilityOff()
			
        self.contour_actors_coronal["c{0}".format(plan)].SetMapper(self.contour_mappers_coronal["c{0}".format(plan)])
        self.contour_actors_coronal["c{0}".format(plan)].GetProperty().SetColor(color)
        self.contour_actors_coronal["c{0}".format(plan)].GetProperty().SetOpacity(opacity)

		

		
		
    def set_contours_color_and_pattern(self, contourid, probability, color, opacity):
	
		#Good settings:    | Settings for image:
		# Point size: 4    | 6
		# Line width: 3.5  | 5.5
	
        if probability == 0:
            self.contour_actors_axial["c{0}".format(contourid)].GetProperty().SetColor(color)
            self.contour_actors_axial["c{0}".format(contourid)].GetProperty().SetOpacity(opacity)
            self.contour_actors_axial["c{0}".format(contourid)].GetProperty().SetLineStipplePattern(0xf0ff)
            self.contour_actors_axial["c{0}".format(contourid)].GetProperty().SetLineStippleRepeatFactor(1)
            self.contour_actors_axial["c{0}".format(contourid)].GetProperty().SetPointSize(4)
            self.contour_actors_axial["c{0}".format(contourid)].GetProperty().SetLineWidth(3.5)
			#before: 3 point size and 3 linewidth
            self.contour_actors_sagittal["c{0}".format(contourid)].GetProperty().SetColor(color)
            self.contour_actors_sagittal["c{0}".format(contourid)].GetProperty().SetOpacity(opacity)
            self.contour_actors_sagittal["c{0}".format(contourid)].GetProperty().SetLineStipplePattern(0xf0ff)
            self.contour_actors_sagittal["c{0}".format(contourid)].GetProperty().SetLineStippleRepeatFactor(1)
            self.contour_actors_sagittal["c{0}".format(contourid)].GetProperty().SetPointSize(4)
            self.contour_actors_sagittal["c{0}".format(contourid)].GetProperty().SetLineWidth(3.5)
			
            self.contour_actors_coronal["c{0}".format(contourid)].GetProperty().SetColor(color)
            self.contour_actors_coronal["c{0}".format(contourid)].GetProperty().SetOpacity(opacity)
            self.contour_actors_coronal["c{0}".format(contourid)].GetProperty().SetLineStipplePattern(0xf0ff)
            self.contour_actors_coronal["c{0}".format(contourid)].GetProperty().SetLineStippleRepeatFactor(1)
            self.contour_actors_coronal["c{0}".format(contourid)].GetProperty().SetPointSize(4)
            self.contour_actors_coronal["c{0}".format(contourid)].GetProperty().SetLineWidth(3.5)
        else:
            self.contour_actors_axial["c{0}".format(contourid)].GetProperty().SetColor(color)
            self.contour_actors_axial["c{0}".format(contourid)].GetProperty().SetOpacity(opacity)
            self.contour_actors_axial["c{0}".format(contourid)].GetProperty().SetLineStipplePattern(0xffff)
            self.contour_actors_axial["c{0}".format(contourid)].GetProperty().SetLineStippleRepeatFactor(1)
            self.contour_actors_axial["c{0}".format(contourid)].GetProperty().SetPointSize(4)
            self.contour_actors_axial["c{0}".format(contourid)].GetProperty().SetLineWidth(3.5)
		
            self.contour_actors_sagittal["c{0}".format(contourid)].GetProperty().SetColor(color)
            self.contour_actors_sagittal["c{0}".format(contourid)].GetProperty().SetOpacity(opacity)
            self.contour_actors_sagittal["c{0}".format(contourid)].GetProperty().SetLineStipplePattern(0xffff)
            self.contour_actors_sagittal["c{0}".format(contourid)].GetProperty().SetLineStippleRepeatFactor(1)
            self.contour_actors_sagittal["c{0}".format(contourid)].GetProperty().SetPointSize(4)
            self.contour_actors_sagittal["c{0}".format(contourid)].GetProperty().SetLineWidth(3.5)
			
            self.contour_actors_coronal["c{0}".format(contourid)].GetProperty().SetColor(color)
            self.contour_actors_coronal["c{0}".format(contourid)].GetProperty().SetOpacity(opacity)
            self.contour_actors_coronal["c{0}".format(contourid)].GetProperty().SetLineStipplePattern(0xffff)
            self.contour_actors_coronal["c{0}".format(contourid)].GetProperty().SetLineStippleRepeatFactor(1)
            self.contour_actors_coronal["c{0}".format(contourid)].GetProperty().SetPointSize(4)
            self.contour_actors_coronal["c{0}".format(contourid)].GetProperty().SetLineWidth(3.5)
			
		
    def set_outlier_contours_to_dark(self, outlier, color):
		
		self.contour_actors_axial["c{0}".format(outlier)].GetProperty().SetColor(color)
		self.contour_actors_axial["c{0}".format(outlier)].GetProperty().SetLineStipplePattern(0xf0ff)
		self.contour_actors_axial["c{0}".format(outlier)].GetProperty().SetLineStippleRepeatFactor(1)
		self.contour_actors_axial["c{0}".format(outlier)].GetProperty().SetPointSize(4)
		self.contour_actors_axial["c{0}".format(outlier)].GetProperty().SetLineWidth(3.5)
				
		self.contour_actors_sagittal["c{0}".format(outlier)].GetProperty().SetColor(color)
		self.contour_actors_sagittal["c{0}".format(outlier)].GetProperty().SetLineStipplePattern(0xf0ff)
		self.contour_actors_sagittal["c{0}".format(outlier)].GetProperty().SetLineStippleRepeatFactor(1)
		self.contour_actors_sagittal["c{0}".format(outlier)].GetProperty().SetPointSize(4)
		self.contour_actors_sagittal["c{0}".format(outlier)].GetProperty().SetLineWidth(3.5)
				
		self.contour_actors_coronal["c{0}".format(outlier)].GetProperty().SetColor(color)
		self.contour_actors_coronal["c{0}".format(outlier)].GetProperty().SetLineStipplePattern(0xf0ff)
		self.contour_actors_coronal["c{0}".format(outlier)].GetProperty().SetLineStippleRepeatFactor(1)
		self.contour_actors_coronal["c{0}".format(outlier)].GetProperty().SetPointSize(4)
		self.contour_actors_coronal["c{0}".format(outlier)].GetProperty().SetLineWidth(3.5)
			
    def set_contour_color(self, contour, color):
	
		#Good settings:   | Other settings:
		# Point size: 5   | 8
		# Line width: 4   | 7
	
        self.contour_actors_axial["c{0}".format(contour)].GetProperty().SetColor(color)
        self.contour_actors_axial["c{0}".format(contour)].GetProperty().SetOpacity(0.99)
        self.contour_actors_axial["c{0}".format(contour)].GetProperty().SetLineStipplePattern(0xffff)
        self.contour_actors_axial["c{0}".format(contour)].GetProperty().SetLineStippleRepeatFactor(1)
        self.contour_actors_axial["c{0}".format(contour)].GetProperty().SetPointSize(5)
        self.contour_actors_axial["c{0}".format(contour)].GetProperty().SetLineWidth(4)
				
        self.contour_actors_sagittal["c{0}".format(contour)].GetProperty().SetColor(color)
        self.contour_actors_sagittal["c{0}".format(contour)].GetProperty().SetOpacity(0.99)
        self.contour_actors_sagittal["c{0}".format(contour)].GetProperty().SetLineStipplePattern(0xffff)
        self.contour_actors_sagittal["c{0}".format(contour)].GetProperty().SetLineStippleRepeatFactor(1)
        self.contour_actors_sagittal["c{0}".format(contour)].GetProperty().SetPointSize(5)
        self.contour_actors_sagittal["c{0}".format(contour)].GetProperty().SetLineWidth(4)
				
        self.contour_actors_coronal["c{0}".format(contour)].GetProperty().SetColor(color)
        self.contour_actors_coronal["c{0}".format(contour)].GetProperty().SetOpacity(1)
        self.contour_actors_coronal["c{0}".format(contour)].GetProperty().SetLineStipplePattern(0xffff)
        self.contour_actors_coronal["c{0}".format(contour)].GetProperty().SetLineStippleRepeatFactor(1)
        self.contour_actors_coronal["c{0}".format(contour)].GetProperty().SetPointSize(5)
        self.contour_actors_coronal["c{0}".format(contour)].GetProperty().SetLineWidth(4)
			
		#before: pointsize was 2 and linewidth was 1.5
			
    def set_isovalue(self, isovalue):
        for x in range(self.nr_doseplans):
            self.contours_axial["c{0}".format(x)].SetValue(0,float(isovalue))
            self.contours_sagittal["c{0}".format(x)].SetValue(0,float(isovalue))
            self.contours_coronal["c{0}".format(x)].SetValue(0,float(isovalue))
		
			

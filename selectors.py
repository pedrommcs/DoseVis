
"""Select indices from a matplotlib collection using `LassoSelector`.

    Selected indices are saved in the `ind` attribute. This tool highlights
    selected points by fading them out (i.e., reducing their alpha values).
    If your collection has alpha < 1, this tool will permanently alter them.

    Note that this tool selects collection objects based on their *origins*
    (i.e., `offsets`).

    Parameters
    ----------
    ax : :class:`~matplotlib.axes.Axes`
        Axes to interact with.

    collection : :class:`matplotlib.collections.Collection` subclass
        Collection you want to select from.

    alpha_other : 0 <= float <= 1
        To highlight a selection, this tool sets all selected points to an
        alpha value of 1 and non-selected points to `alpha_other`.
    """
	
import numpy as np
from matplotlib.widgets import LassoSelector
from matplotlib.path import Path
import vtk
	
class SelectFromCollection(object):

    def __init__(self, viewer, ax, collection, alpha_other=0.3):
        self.canvas = ax.figure.canvas
        self.collection = collection
        self.viewer = viewer
        self.alpha_other = alpha_other

        self.xys = collection.get_offsets()
        self.Npts = len(self.xys)

        # Ensure that we have separate colors for each object
        self.fc = collection.get_facecolors()
        #self.collection.set_facecolors('red')
        
        if len(self.fc) == 0:
            raise ValueError('Collection must have a facecolor')
        elif len(self.fc) == 1:
            self.fc = np.tile(self.fc, self.Npts).reshape(self.Npts, -1)

        self.lasso = LassoSelector(ax, onselect=self.onselect)
        self.ind = []

    def onselect(self, verts):
        voxels_xyz = []
        path = Path(verts)
        self.ind = np.nonzero([path.contains_point(xy) for xy in self.xys])[0]
        
        for i in self.ind:
            voxel_xyz = self.viewer.coordinates[i]
            voxel_xyz.append(self.viewer.meanx[i])
            voxels_xyz.append(voxel_xyz)
		
		# light blue: 0.1, 1, 1
		
        self.fc[:, 0] = 0
        self.fc[:, 1] = 0
        self.fc[:, 2] = 1
        self.fc[:, -1] = self.alpha_other
		
        self.fc[self.ind, 0] = 1
        self.fc[self.ind, 1] = 1
        self.fc[self.ind, 2] = 0
        self.fc[self.ind, -1] = 1
		
		
        self.collection.set_facecolors(self.fc)
        self.canvas.draw_idle()
        #self.canvas.draw()
		
        self.highlight_voxels_2D(voxels_xyz)
        #self.canvas.draw_idle()
        self.highlight_voxels_3D(voxels_xyz)

		
		
    def highlight_voxels_2D(self, coords):
        newimage = vtk.vtkImageData()
        newimage.SetSpacing(self.viewer.doseplans["p1"].GetSpacing())
        newimage.SetOrigin(self.viewer.doseplans["p1"].GetOrigin())
        newimage.SetDimensions(self.viewer.doseplans["p1"].GetDimensions())
        newimage.SetExtent(self.viewer.doseplans["p1"].GetExtent())
        newimage.SetNumberOfScalarComponents(1)
        newimage.SetScalarTypeToDouble()
        newimage.AllocateScalars()

        for p in coords:
		    newimage.SetScalarComponentFromDouble(p[0],p[1],p[2],0, 60)
			
        flipYFilter = vtk.vtkImageFlip()
        flipYFilter.SetFilteredAxis(1)
        flipYFilter.SetInput(newimage)
        flipYFilter.Update()
			
        self.viewer.refresh_2d(flipYFilter.GetOutput())
		
		
		
    def highlight_voxels_3D(self, coords):

        self.viewer.ren_iso.RemoveVolume(self.viewer.vol)

        newimage = vtk.vtkImageData()
        newimage.SetSpacing(self.viewer.volumedata.GetSpacing())
        newimage.SetOrigin(self.viewer.volumedata.GetOrigin())
        newimage.SetDimensions(self.viewer.volumedata.GetDimensions())
        newimage.SetExtent(self.viewer.volumedata.GetExtent())
        newimage.SetNumberOfScalarComponents(1)
        newimage.SetScalarTypeToDouble()
        newimage.AllocateScalars()

        for p in coords:
		    newimage.SetScalarComponentFromDouble(p[0],p[1],p[2],0, p[3])
			
			
        shift_scale = vtk.vtkImageShiftScale()
        shift_scale.SetInput(newimage)
        shift_scale.SetOutputScalarTypeToUnsignedChar()
        shift_scale.Update()
		
        flipYFilter = vtk.vtkImageFlip()
        flipYFilter.SetFilteredAxis(1)
        flipYFilter.SetInput(shift_scale.GetOutput())
        flipYFilter.Update()
		
        self.viewer.volMapper.SetInput(flipYFilter.GetOutput())
		
        self.viewer.ren_iso.AddVolume(self.viewer.vol)
        self.viewer.refresh_3d()
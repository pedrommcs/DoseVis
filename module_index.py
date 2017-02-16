class EnsembleViewer:
    kits = ['vtk_kit']
    cats = ['Viewers']
    help = """Module to visualize variability across an ensemble of radiotherapy dose plans.
	
	The core aspect of the module is the ability of providing insight on the variability at two different levels:\n
	- First, through the iso-contours across the dose plans.\n
	- Secondly, at a voxel level.\n
	
	The user interface consists of three views: uploads view, contour-based view and voxel-based view.
	
	The uploads view allows the user to load the necessary data files. The view was flexibly designed to support multiple instances.
	After the files have been loaded, the user can perform the visualization analysis at a contour-level and at a voxel-level.
	
	#--------------------------CONTOUR BASED VIEW------------------------------
	
    The contour perspective consists of six different elements, which can be grouped into two complementary views: anatomical view and analysis view.
	
	- The anatomical view contains 2D representations of the volume and dose plans data (axial,sagittal and coronal).\n
    - The analysis view contains the elements that enable the analysis of variability (operation panel, barchart, heatmap)\n
	
	#--------------------------VOXEL BASED VIEW------------------------------
	
	The voxel perspective consists of four equally sized views.
	- An axial view, which corresponds to the same axial view in the contour perspective.\n
	- A distribution plot view, where the underlying value distribution is displayed when probing or selecting a region in the axial view.\n
	- A scatter plot view, displaying all the voxels as points in a graph.\n
	- A volume rendering view, containing a three dimensional representation of the average dose plan.\n
    """

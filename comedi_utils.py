# Copyright (c) Charl P. Botha, TU Delft.
# All rights reserved.
# See COPYRIGHT for details.
# ---------------------------------------
# Edited by Corine Slagboom & Noeska Smit to add possibility of adding overlay to the sliceviewer and some special synching.
# And by edited we mean mutilated :)

from module_kits.vtk_kit.utils import DVOrientationWidget
import operator
import vtk
import wx

class SyncSliceViewers:
    """Class to link a number of CMSliceViewer instances w.r.t.
    camera.

    FIXME: consider adding option to block certain slice viewers from
    participation.  Is this better than just removing them?
    """

    def __init__(self):
        # store all slice viewer instances that are being synced
        self.slice_viewers = []
        # edit nnsmit
        self.slice_viewers2 = []
        # end edit
        self.observer_tags = {}
        # if set to False, no syncing is done.
        # user is responsible for doing the initial sync with sync_all
        # after this variable is toggled from False to True
        self.sync = True

    def add_slice_viewer(self, slice_viewer):
        if slice_viewer in self.slice_viewers:
            return

        # we'll use this to store all observer tags for this
        # slice_viewer
        t = self.observer_tags[slice_viewer] = {}


        istyle = slice_viewer.rwi.GetInteractorStyle()

        # the following two observers are workarounds for a bug in VTK
        # the interactorstyle does NOT invoke an InteractionEvent at
        # mousewheel, so we make sure it does in our workaround
        # observers.
        '''t['istyle MouseWheelForwardEvent'] = \
                istyle.AddObserver('MouseWheelForwardEvent',
                self._observer_mousewheel_forward)

        t['istyle MouseWheelBackwardEvent'] = \
                istyle.AddObserver('MouseWheelBackwardEvent',
                self._observer_mousewheel_backward)

        # this one only gets called for camera interaction (of course)
        t['istyle InteractionEvent'] = \
                istyle.AddObserver('InteractionEvent',
                lambda o,e: self._observer_camera(slice_viewer))'''

        # this gets call for all interaction with the slice
        # (cursoring, slice pushing, perhaps WL)
        for idx in range(3):
            # note the i=idx in the lambda expression.  This is
            # because that gets evaluated at define time, whilst the
            # body of the lambda expression gets evaluated at
            # call-time
            '''t['ipw%d InteractionEvent' % (idx,)] = \
                slice_viewer.ipws[idx].AddObserver('InteractionEvent',
                lambda o,e,i=idx: self._observer_ipw(slice_viewer, i))'''

            t['ipw%d WindowLevelEvent' % (idx,)] = \
                slice_viewer.ipws[idx].AddObserver('WindowLevelEvent',
                lambda o,e,i=idx: self._observer_window_level(slice_viewer,i))

        self.slice_viewers.append(slice_viewer)
    
    # edit nnsmit
    # not the prettiest 'fix' in the book, but unfortunately short on time     
    def add_slice_viewer2(self, slice_viewer):
        if slice_viewer in self.slice_viewers:
            return

        # we'll use this to store all observer tags for this
        # slice_viewer
        t = self.observer_tags[slice_viewer] = {}


        istyle = slice_viewer.rwi.GetInteractorStyle()

        # the following two observers are workarounds for a bug in VTK
        # the interactorstyle does NOT invoke an InteractionEvent at
        # mousewheel, so we make sure it does in our workaround
        # observers.
        t['istyle MouseWheelForwardEvent'] = \
                istyle.AddObserver('MouseWheelForwardEvent',
                self._observer_mousewheel_forward)

        t['istyle MouseWheelBackwardEvent'] = \
                istyle.AddObserver('MouseWheelBackwardEvent',
                self._observer_mousewheel_backward)

        # this gets call for all interaction with the slice
        for idx in range(3):
            # note the i=idx in the lambda expression.  This is
            # because that gets evaluated at define time, whilst the
            # body of the lambda expression gets evaluated at
            # call-time
            t['ipw%d InteractionEvent' % (idx,)] = \
                slice_viewer.ipws[idx].AddObserver('InteractionEvent',
                lambda o,e,i=idx: self._observer_ipw(slice_viewer, i))

        self.slice_viewers2.append(slice_viewer)    
    #end edit

    def close(self):
        for sv in self.slice_viewers:
            self.remove_slice_viewer(sv)

    def _observer_camera(self, sv):
        """This observer will keep the cameras of all the
        participating slice viewers synched.

        It's only called when the camera is moved.
        """
        if not self.sync:
            return

        cc = self.sync_cameras(sv)
        [sv.render() for sv in cc]

    def _observer_mousewheel_forward(self, vtk_o, vtk_e):
        vtk_o.OnMouseWheelForward()
        vtk_o.InvokeEvent('InteractionEvent')

    def _observer_mousewheel_backward(self, vtk_o, vtk_e):
        vtk_o.OnMouseWheelBackward()
        vtk_o.InvokeEvent('InteractionEvent')

    def _observer_ipw(self, slice_viewer, idx=0):
        """This is called whenever the user does ANYTHING with the
        IPW.
        """
        if not self.sync:
            return

        cc = self.sync_ipws(slice_viewer, idx)
        [sv.render() for sv in cc]

    def _observer_window_level(self, slice_viewer, idx=0):
        """This is called whenever the window/level is changed.  We
        don't have to render, because the SetWindowLevel() call does
        that already.
        """
        if not self.sync:
            return

        self.sync_window_level(slice_viewer, idx)

    def remove_slice_viewer(self, slice_viewer):
        if slice_viewer in self.slice_viewers:

            # first remove all observers that we might have added
            t = self.observer_tags[slice_viewer]
            istyle = slice_viewer.rwi.GetInteractorStyle()
            istyle.RemoveObserver(
                    t['istyle InteractionEvent'])
            istyle.RemoveObserver(
                    t['istyle MouseWheelForwardEvent'])
            istyle.RemoveObserver(
                    t['istyle MouseWheelBackwardEvent'])

            for idx in range(3):
                ipw = slice_viewer.ipws[idx]
                ipw.RemoveObserver(
                    t['ipw%d InteractionEvent' % (idx,)])
                ipw.RemoveObserver(
                    t['ipw%d WindowLevelEvent' % (idx,)])

            # then delete our record of these observer tags
            del self.observer_tags[slice_viewer]

            # then delete our record of the slice_viewer altogether
            idx = self.slice_viewers.index(slice_viewer)
            del self.slice_viewers[idx]

    def sync_cameras(self, sv, dest_svs=None):
        """Sync all cameras to that of sv.

        Returns a list of changed SVs (so that you know which ones to
        render).
        """
        cam = sv.renderer.GetActiveCamera()
        pos = cam.GetPosition()
        fp = cam.GetFocalPoint()
        vu = cam.GetViewUp()
        ps = cam.GetParallelScale()

        if dest_svs is None:
            dest_svs = self.slice_viewers

        changed_svs = []
        for other_sv in dest_svs:
            if not other_sv is sv:
                other_ren = other_sv.renderer
                other_cam = other_ren.GetActiveCamera()
                other_cam.SetPosition(pos)
                other_cam.SetFocalPoint(fp)
                other_cam.SetViewUp(vu)
                # you need this too, else the parallel mode does not
                # synchronise.
                other_cam.SetParallelScale(ps)
                other_ren.UpdateLightsGeometryToFollowCamera()
                other_ren.ResetCameraClippingRange()
                changed_svs.append(other_sv)

        return changed_svs

    def sync_ipws(self, sv, idx=0, dest_svs=None):
        """Sync all slice positions to that of sv.

        Returns a list of changed SVs so that you know on which to
        call render.
        """
        ipw = sv.ipws[idx]
        o,p1,p2 = ipw.GetOrigin(), \
                ipw.GetPoint1(), ipw.GetPoint2()

        if dest_svs is None:
            dest_svs = self.slice_viewers
        changed_svs = []
        for other_sv in dest_svs:
            if other_sv is not sv:
                # nnsmit edit
                if other_sv.overlay_active == 1:
                    for i, ipw_overlay in enumerate(other_sv.overlay_ipws):
                        other_sv.observer_sync_overlay(sv.ipws,i)
                # end edit
                other_ipw = other_sv.ipws[idx]
                # we only synchronise slice position if it's actually
                # changed.
                if o != other_ipw.GetOrigin() or \
                        p1 != other_ipw.GetPoint1() or \
                        p2 != other_ipw.GetPoint2():
                    other_ipw.SetOrigin(o)
                    other_ipw.SetPoint1(p1)
                    other_ipw.SetPoint2(p2)
                    other_ipw.UpdatePlacement()
                    changed_svs.append(other_sv)

        # edit nnsmit
        # This fix is so nasty it makes me want to cry
        # TODO fix it properly :)
        if len(self.slice_viewers2) != 0:
            for other_sv in self.slice_viewers2:
                if other_sv is not sv:
                    if other_sv.overlay_active == 1:
                        for i, ipw_overlay in enumerate(other_sv.overlay_ipws):
                            other_sv.observer_sync_overlay(sv.ipws,i)
                    other_ipw = other_sv.ipws[idx]
                    # we only synchronise slice position if it's actually
                    # changed.
                    if o != other_ipw.GetOrigin() or \
                            p1 != other_ipw.GetPoint1() or \
                            p2 != other_ipw.GetPoint2():
                        other_ipw.SetOrigin(o)
                        other_ipw.SetPoint1(p1)
                        other_ipw.SetPoint2(p2)
                        other_ipw.UpdatePlacement()
                        other_sv.render()
        # end edit
         
        return changed_svs

    def sync_window_level(self, sv, idx=0, dest_svs=None):
        """Sync all window level settings with that of SV.

        Returns list of changed SVs: due to the SetWindowLevel call,
        these have already been rendered!
        """

        ipw = sv.ipws[idx]
        w,l = ipw.GetWindow(), ipw.GetLevel()

        if dest_svs is None:
            dest_svs = self.slice_viewers

        changed_svs = []
        for other_sv in dest_svs:
            if other_sv is not sv:
                other_ipw = other_sv.ipws[idx]

                if w != other_ipw.GetWindow() or \
                        l != other_ipw.GetLevel():
                            other_ipw.SetWindowLevel(w,l,0)
                            changed_svs.append(other_sv)
                            other_sv.render()


        return changed_svs

    def sync_all(self, sv, dest_svs=None):
        """Convenience function that performs all syncing possible of
        dest_svs to sv.  It also take care of making only the
        necessary render calls.
        """

        # FIXME: take into account all other slices too.
        c1 = set(self.sync_cameras(sv, dest_svs))
        c2 = set(self.sync_ipws(sv, 0, dest_svs))
        c3 = set(self.sync_window_level(sv, 0, dest_svs))

        # we only need to call render on SVs that are in c1 or c2, but
        # NOT in c3, because WindowLevel syncing already does a
        # render.  Use set operations for this: 
        c4 = (c1 | c2) - c3
        [isv.render() for isv in c4]

###########################################################################

###########################################################################


class CMSliceViewer:
    """Simple class for enabling 1 or 3 ortho slices in a 3D scene.
    """

    def __init__(self, rwi, renderer):
        # nnsmit-edit
        self.overlay_active = 0;
        self.overlay_active_voxels = 0;
        self.overlay_active_100band1 = 0;
        self.overlay_active_100band2 = 0;
        self.overlay_active_100band3 = 0;
        self.overlay_active_50band1 = 0;
        self.overlay_active_50band2 = 0;
        self.overlay_active_50band3 = 0;		
		
        # end edit
        self.rwi = rwi
        self.renderer = renderer

        istyle = vtk.vtkInteractorStyleTrackballCamera()
        rwi.SetInteractorStyle(istyle)

        # we unbind the existing mousewheel handler so it doesn't
        # interfere
        rwi.Unbind(wx.EVT_MOUSEWHEEL)
        rwi.Bind(wx.EVT_MOUSEWHEEL, self._handler_mousewheel)

        self.ipws = [vtk.vtkImagePlaneWidget() for _ in range(3)]
        lut = self.ipws[0].GetLookupTable()
        for ipw in self.ipws:
            ipw.SetInteractor(rwi)
            ipw.SetLookupTable(lut)

	    # IPWS for overlay
    	self.overlay_ipws = [vtk.vtkImagePlaneWidget() for _ in range(3)]
        lut = self.overlay_ipws[0].GetLookupTable()
        lut.SetNumberOfTableValues(3)
        lut.SetTableValue(0,0,0,0,0)
        lut.SetTableValue(1,0.5,0,1,1)
        lut.SetTableValue(2,1,0,0,1)
        lut.Build()
        for ipw_overlay in self.overlay_ipws:
            ipw_overlay.SetInteractor(rwi)
            ipw_overlay.SetLookupTable(lut)
            ipw_overlay.AddObserver('InteractionEvent', wx.EVT_MOUSEWHEEL)

	
	    # IPWS for voxels selected in scatterplot
    	self.overlay_ipws_voxels = [vtk.vtkImagePlaneWidget() for _ in range(3)]
        lut = self.overlay_ipws_voxels[0].GetLookupTable()
        lut.SetNumberOfTableValues(3)
        lut.SetTableValue(0,0,0,0,0)
        lut.SetTableValue(1,0.5,0,1,1)
        lut.SetTableValue(2,1,0,0,1)
        lut.Build()
        for ipw_overlay in self.overlay_ipws_voxels:
            ipw_overlay.SetInteractor(rwi)
            ipw_overlay.SetLookupTable(lut)
            ipw_overlay.AddObserver('InteractionEvent', wx.EVT_MOUSEWHEEL)	
	
			
			
	    # IPWS for overlay of 100%band in first row
    	self.overlay_ipws_100band1 = [vtk.vtkImagePlaneWidget() for _ in range(3)]
        lut1 = self.overlay_ipws_100band1[0].GetLookupTable()
        lut1.SetNumberOfTableValues(3)
        lut1.SetTableValue(0,0,0,0,0)
        lut1.SetTableValue(1, 1, 1, 0, 1)
        lut1.SetTableValue(2, 1,1,0, 1)
        lut1.Modified()
        lut1.Build()
        for ipw_overlay in self.overlay_ipws_100band1:
            ipw_overlay.SetInteractor(rwi)
            ipw_overlay.SetLookupTable(lut1)
            ipw_overlay.AddObserver('InteractionEvent', wx.EVT_MOUSEWHEEL)
			
	    # IPWS for overlay of 50%band in first row
    	self.overlay_ipws_50band1 = [vtk.vtkImagePlaneWidget() for _ in range(3)]
        lut1 = self.overlay_ipws_50band1[0].GetLookupTable()
        lut1.SetNumberOfTableValues(3)
        lut1.SetTableValue(0,0,0,0,0)
        lut1.SetTableValue(1, 1, 1, 0, 1)
        lut1.SetTableValue(2, 1,1,0, 1)
        lut1.Modified()
        lut1.Build()
        for ipw_overlay in self.overlay_ipws_50band1:
            ipw_overlay.SetInteractor(rwi)
            ipw_overlay.SetLookupTable(lut1)
            ipw_overlay.AddObserver('InteractionEvent', wx.EVT_MOUSEWHEEL)
			
			
	    # IPWS for overlay of 100%band in second row
    	self.overlay_ipws_100band2 = [vtk.vtkImagePlaneWidget() for _ in range(3)]
        #lut2 = self.overlay_ipws_100band2[0].GetLookupTable()
        #lut2.SetNumberOfTableValues(3)
        #lut2.SetTableValue(0,0,0,0,0)
        #lut2.SetTableValue(1, 0.98,0,0, 0.37)
        #lut2.SetTableValue(2, 0.98,0,0, 0.37)
        #lut2.Modified()
        #lut2.Build()
        for ipw_overlay in self.overlay_ipws_100band2:
            ipw_overlay.SetInteractor(rwi)
            #ipw_overlay.SetLookupTable(lut2)
            ipw_overlay.AddObserver('InteractionEvent', wx.EVT_MOUSEWHEEL)
			
	    # IPWS for overlay of 100%band in second row
    	self.overlay_ipws_50band2 = [vtk.vtkImagePlaneWidget() for _ in range(3)]
        #lut2 = self.overlay_ipws_100band2[0].GetLookupTable()
        #lut2.SetNumberOfTableValues(3)
        #lut2.SetTableValue(0,0,0,0,0)
        #lut2.SetTableValue(1, 0.98,0,0, 0.37)
        #lut2.SetTableValue(2, 0.98,0,0, 0.37)
        #lut2.Modified()
        #lut2.Build()
        for ipw_overlay in self.overlay_ipws_50band2:
            ipw_overlay.SetInteractor(rwi)
            #ipw_overlay.SetLookupTable(lut2)
            ipw_overlay.AddObserver('InteractionEvent', wx.EVT_MOUSEWHEEL)
			
			
	    # IPWS for overlay of 100%band in third row
    	self.overlay_ipws_100band3 = [vtk.vtkImagePlaneWidget() for _ in range(3)]
        lut3 = self.overlay_ipws_100band3[0].GetLookupTable()
        lut3.SetNumberOfTableValues(3)
        lut3.SetTableValue(0,0,0,0,0)
        lut3.SetTableValue(1,0,0.643,0.941, 0.5)
        lut3.SetTableValue(2,0,0.643,0.941, 0.5)
        lut3.Modified()
        lut3.Build()
        for ipw_overlay in self.overlay_ipws_100band3:
            ipw_overlay.SetInteractor(rwi)
            ipw_overlay.SetLookupTable(lut3)
            ipw_overlay.AddObserver('InteractionEvent', wx.EVT_MOUSEWHEEL)
			
	    # IPWS for overlay of 50%band in third row
    	self.overlay_ipws_50band3 = [vtk.vtkImagePlaneWidget() for _ in range(3)]
        lut3 = self.overlay_ipws_50band3[0].GetLookupTable()
        lut3.SetNumberOfTableValues(3)
        lut3.SetTableValue(0,0,0,0,0)
        lut3.SetTableValue(1,0,0.643,0.941, 0.5)
        lut3.SetTableValue(2,0,0.643,0.941, 0.5)
        lut3.Modified()
        lut3.Build()
        for ipw_overlay in self.overlay_ipws_50band3:
            ipw_overlay.SetInteractor(rwi)
            ipw_overlay.SetLookupTable(lut3)
            ipw_overlay.AddObserver('InteractionEvent', wx.EVT_MOUSEWHEEL)
	
	
        # now actually connect the sync_overlay observer
        for i,ipw in enumerate(self.ipws):
            ipw.AddObserver('InteractionEvent',lambda vtk_o, vtk_e, i=i: self.observer_sync_overlay(self.ipws,i))
        # end edit

        # we only set the picker on the visible IPW, else the
        # invisible IPWs block picking!
        self.picker = vtk.vtkCellPicker()
        self.picker.SetTolerance(0.005)
        self.ipws[0].SetPicker(self.picker)

        self.outline_source = vtk.vtkOutlineCornerFilter()
        m = vtk.vtkPolyDataMapper()
        m.SetInput(self.outline_source.GetOutput())
        a = vtk.vtkActor()
        a.SetMapper(m)
        a.PickableOff()
        self.outline_actor = a

        self.dv_orientation_widget = DVOrientationWidget(rwi)

        # this can be used by clients to store the current world
        # position
        self.current_world_pos = (0,0,0)
        self.current_index_pos = (0,0,0)

	# nnsmit-edit
    def observer_sync_overlay(self,ipws,ipw_idx):
	    # get the primary IPW
        pipw = ipws[ipw_idx]
        # get the overlay IPW
        oipw = self.overlay_ipws[ipw_idx] 
		
        #get the voxels overlay IPW
        oipwvoxels = self.overlay_ipws_voxels[ipw_idx]
		
		#get the overlay IPW for 100%band in first row 
        oipw100r1 = self.overlay_ipws_100band1[ipw_idx]
		#get the overlay IPW for 50%band in first row 
        oipw50r1 = self.overlay_ipws_50band1[ipw_idx] 

		#get the overlay IPW for 100%band in second row 
        oipw100r2 = self.overlay_ipws_100band2[ipw_idx]
		#get the overlay IPW for 100%band in second row 
        oipw50r2 = self.overlay_ipws_50band2[ipw_idx] 
		
		#get the overlay IPW for 100%band in third row 
        oipw100r3 = self.overlay_ipws_100band3[ipw_idx]
		#get the overlay IPW for 50%band in third row 
        oipw50r3 = self.overlay_ipws_50band3[ipw_idx] 
		
        # get plane geometry from primary
        o,p1,p2 = pipw.GetOrigin(),pipw.GetPoint1(),pipw.GetPoint2()
        # and apply to the overlay
        oipw.SetOrigin(o)
        oipw.SetPoint1(p1)
        oipw.SetPoint2(p2)
        oipw.UpdatePlacement()

        oipwvoxels.SetOrigin(o)
        oipwvoxels.SetPoint1(p1)
        oipwvoxels.SetPoint2(p2)
        oipwvoxels.UpdatePlacement()
		
        oipw100r1.SetOrigin(o)
        oipw100r1.SetPoint1(p1)
        oipw100r1.SetPoint2(p2)
        oipw100r1.UpdatePlacement()   
		
        oipw50r1.SetOrigin(o)
        oipw50r1.SetPoint1(p1)
        oipw50r1.SetPoint2(p2)
        oipw50r1.UpdatePlacement()   
		
        oipw100r2.SetOrigin(o)
        oipw100r2.SetPoint1(p1)
        oipw100r2.SetPoint2(p2)
        oipw100r2.UpdatePlacement()
		
        oipw50r2.SetOrigin(o)
        oipw50r2.SetPoint1(p1)
        oipw50r2.SetPoint2(p2)
        oipw50r2.UpdatePlacement()
		
        oipw100r3.SetOrigin(o)
        oipw100r3.SetPoint1(p1)
        oipw100r3.SetPoint2(p2)
        oipw100r3.UpdatePlacement()
		
        oipw50r3.SetOrigin(o)
        oipw50r3.SetPoint1(p1)
        oipw50r3.SetPoint2(p2)
        oipw50r3.UpdatePlacement()  
		
    # end edit

    def close(self):
        self.set_input(None)
        self.dv_orientation_widget.close()
        self.set_overlay_input(None)
        self.set_overlay_input_voxels(None)
        self.set_overlay_input_axial_100band1(None)
        self.set_overlay_input_sagittal_100band1(None)
        self.set_overlay_input_coronal_100band1(None)
        self.set_overlay_input_axial_100band2(None)
        self.set_overlay_input_sagittal_100band2(None)
        self.set_overlay_input_coronal_100band2(None)
        self.set_overlay_input_axial_100band3(None)
        self.set_overlay_input_sagittal_100band3(None)
        self.set_overlay_input_coronal_100band3(None)
        self.set_overlay_input_axial_50band1(None)
        self.set_overlay_input_sagittal_50band1(None)
        self.set_overlay_input_coronal_50band1(None)
        self.set_overlay_input_axial_50band2(None)
        self.set_overlay_input_sagittal_50band2(None)
        self.set_overlay_input_coronal_50band2(None)
        self.set_overlay_input_axial_50band3(None)
        self.set_overlay_input_sagittal_50band3(None)
        self.set_overlay_input_coronal_50band3(None)

    def activate_slice(self, idx):
        if idx in [1,2]:
            self.ipws[idx].SetEnabled(1)
            self.ipws[idx].SetPicker(self.picker)


    def deactivate_slice(self, idx):
        if idx in [1,2]:
            self.ipws[idx].SetEnabled(0)
            self.ipws[idx].SetPicker(None)

    def get_input(self):
        return self.ipws[0].GetInput()

    def get_world_pos(self, image_pos):
        """Given image coordinates, return the corresponding world
        position.
        """

        idata = self.get_input()
        if not idata:
            return None

        ispacing = idata.GetSpacing()
        iorigin = idata.GetOrigin()
        # calculate real coords
        world = map(operator.add, iorigin,
                    map(operator.mul, ispacing, image_pos[0:3]))


    def set_perspective(self):
        cam = self.renderer.GetActiveCamera()
        cam.ParallelProjectionOff()

    def set_parallel(self):
        cam = self.renderer.GetActiveCamera()
        cam.ParallelProjectionOn()
        
    # nnsmit edit    
    def set_opacity(self,opacity):
        lut = self.ipws[0].GetLookupTable()
        lut.SetAlphaRange(opacity, opacity)
        lut.Build()
        self.ipws[0].SetLookupTable(lut)
    # end edit
    
    def _handler_mousewheel(self, event):
        # event.GetWheelRotation() is + or - 120 depending on
        # direction of turning.
        if event.ControlDown():
            delta = 10
        elif event.ShiftDown():
            delta = 1
        else:
            # if user is NOT doing shift / control, we pass on to the
            # default handling which will give control to the VTK
            # mousewheel handlers.
            self.rwi.OnMouseWheel(event)
            return
            
        if event.GetWheelRotation() > 0:
            self._ipw1_delta_slice(+delta)
        else:
            self._ipw1_delta_slice(-delta)

        self.render()
        self.ipws[0].InvokeEvent('InteractionEvent')

    def _ipw1_delta_slice(self, delta):
        """Move to the delta slices fw/bw, IF the IPW is currently
        aligned with one of the axes.
        """

        ipw = self.ipws[0]
        if ipw.GetPlaneOrientation() < 3:
            ci = ipw.GetSliceIndex()
            ipw.SetSliceIndex(ci + delta)

    def render(self):
        self.rwi.GetRenderWindow().Render()
        # nnsmit edit
        # synch those overlays:
		
        if self.overlay_active == 1:
            for i, ipw_overlay in enumerate(self.overlay_ipws):
                self.observer_sync_overlay(self.ipws, i)
				
        if self.overlay_active_voxels == 1:
            for i, ipw_overlay in enumerate(self.overlay_ipws_voxels):
                self.observer_sync_overlay(self.ipws, i)
	
        if self.overlay_active_100band1 == 1:
            for i, ipw_overlay in enumerate(self.overlay_ipws_100band1):
                self.observer_sync_overlay(self.ipws, i)
        if self.overlay_active_100band2 == 1:
            for i, ipw_overlay in enumerate(self.overlay_ipws_100band2):
                self.observer_sync_overlay(self.ipws, i)
        if self.overlay_active_100band3 == 1:
            for i, ipw_overlay in enumerate(self.overlay_ipws_100band3):
                self.observer_sync_overlay(self.ipws, i)
				
        if self.overlay_active_50band1 == 1:
            for i, ipw_overlay in enumerate(self.overlay_ipws_50band1):
                self.observer_sync_overlay(self.ipws, i)
        if self.overlay_active_50band2 == 1:
            for i, ipw_overlay in enumerate(self.overlay_ipws_50band2):
                self.observer_sync_overlay(self.ipws, i)
        if self.overlay_active_50band3 == 1:
            for i, ipw_overlay in enumerate(self.overlay_ipws_50band3):
                self.observer_sync_overlay(self.ipws, i)
				
				
        # end edit    

    def reset_camera(self):
        self.renderer.ResetCamera()
        cam = self.renderer.GetActiveCamera()
        cam.SetViewUp(0,-1,0)

    def reset_to_default_view(self, view_index):
        """
        @param view_index 2 for XY
        """

        if view_index == 2:
            
            cam = self.renderer.GetActiveCamera()
            # then make sure it's up is the right way
            cam.SetViewUp(0,-1,0)
            # just set the X,Y of the camera equal to the X,Y of the
            # focal point.
            fp = cam.GetFocalPoint()
            cp = cam.GetPosition()
            if cp[2] < fp[2]:
                z = fp[2] + (fp[2] - cp[2])
            else:
                z = cp[2]

            cam.SetPosition(fp[0], fp[1], z)

            # first reset the camera
            self.renderer.ResetCamera() 
        # nnsmit edit
        # synch overlays as well:
		
        if self.overlay_active == 1:
            for i, ipw_overlay in enumerate(self.overlay_ipws):
                ipw_overlay.SetSliceIndex(0)
				
        if self.overlay_active_voxels == 1:
            for i, ipw_overlay in enumerate(self.overlay_ipws_voxels):
                ipw_overlay.SetSliceIndex(0)
		
        if self.overlay_active_100band1 == 1:
            for i, ipw_overlay in enumerate(self.overlay_ipws_100band1):
                ipw_overlay.SetSliceIndex(0) 
        if self.overlay_active_100band2 == 1:
            for i, ipw_overlay in enumerate(self.overlay_ipws_100band2):
                ipw_overlay.SetSliceIndex(0) 	
        if self.overlay_active_100band3 == 1:
            for i, ipw_overlay in enumerate(self.overlay_ipws_100band3):
                ipw_overlay.SetSliceIndex(0)
				
        if self.overlay_active_50band1 == 1:
            for i, ipw_overlay in enumerate(self.overlay_ipws_50band1):
                ipw_overlay.SetSliceIndex(0) 
        if self.overlay_active_50band2 == 1:
            for i, ipw_overlay in enumerate(self.overlay_ipws_50band2):
                ipw_overlay.SetSliceIndex(0) 	
        if self.overlay_active_50band3 == 1:
            for i, ipw_overlay in enumerate(self.overlay_ipws_50band3):
                ipw_overlay.SetSliceIndex(0)
				
        for i, ipw in enumerate(self.ipws):
                ipw.SetWindowLevel(500,-800,0)
        self.render()
        # end edit

    def set_input(self, input):
        ipw = self.ipws[0]
        ipw.DisplayTextOn()
        if input == ipw.GetInput():
            return

        if input is None:
            # remove outline actor, else this will cause errors when
            # we disable the IPWs (they call a render!)
            self.renderer.RemoveViewProp(self.outline_actor)
            self.outline_source.SetInput(None)

            self.dv_orientation_widget.set_input(None)

            for ipw in self.ipws:
                # argh, this disable causes a render
                ipw.SetEnabled(0)
                ipw.SetInput(None)

        else:
            self.outline_source.SetInput(input)
            self.renderer.AddViewProp(self.outline_actor)

            orientations = [2, 0, 1]
            active = [1, 0, 0]
            for i, ipw in enumerate(self.ipws):
                ipw.SetInput(input)
                ipw.SetWindowLevel(500,-800,0)
                ipw.SetPlaneOrientation(orientations[i]) # axial
                ipw.SetSliceIndex(0)
                ipw.SetEnabled(active[i])

            self.dv_orientation_widget.set_input(input)

    # nnsmit-edit
	
	#-------------------------- Set the overlays for the average dose plan color mapping ----------------------------
	
    def set_overlay_input(self, input):
        self.overlay_active = 1
        ipw = self.overlay_ipws[0]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active = 0;
            for ipw_overlay in self.overlay_ipws:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [1, 0, 0]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws):
                self.observer_sync_overlay(self.ipws, i)        
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # axial
                ipw_overlay.SetEnabled(active[i]) 
        self.render()
		
    def set_overlay_inputS(self, input):
        self.overlay_active = 1
        ipw = self.overlay_ipws[1]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active = 0;
            for ipw_overlay in self.overlay_ipws:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [0, 1, 0]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws):
                self.observer_sync_overlay(self.ipws, i)
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # sagittal
                ipw_overlay.SetEnabled(active[i])
        self.render()


    def set_overlay_inputC(self, input):
        self.overlay_active = 1
        ipw = self.overlay_ipws[2]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active = 0;
            for ipw_overlay in self.overlay_ipws:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [0, 0, 1]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws):
                self.observer_sync_overlay(self.ipws, i)
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # coronal
                ipw_overlay.SetEnabled(active[i])
        self.render()
		
		
    def set_overlay_input_voxels(self, input):
        self.overlay_active_voxels = 1
        ipw = self.overlay_ipws_voxels[0]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_voxels = 0;
            for ipw_overlay in self.overlay_ipws_voxels:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [1, 0, 0]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_voxels):
                self.observer_sync_overlay(self.ipws, i)        
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # axial
                ipw_overlay.SetEnabled(active[i]) 
        self.render()
		
	#-------------------------- Set the overlays for the contour bands ----------------------------
	
	'''
	An image plan widget has 3 axes: axial, sagittal and coronal. The set_overlay methods use the ipws. Because the 50%band and the 100%band are different files,
	and also because there are 3 rows with changeable isovalues, it's necessary to create an ipws for every band in every row. This is an hack / Hard coded feature, 
	create specifically for Ensemble Viewer. The nomenclature is:
	
	set_overlay_input_axial_100band1 ---------------------------> Set overlay for 100% band in row 1, in axial plane ------------|
	set_overlay_input_sagittal_100band1 ------------------------> Set overlay for 100% band in row 1, in sagittal plane          |  overlay_ipws_100band1, overlay_active_100band1
	set_overlay_input_coronal_100band1	------------------------> Set overlay for 100% band in row 1, in coronal plane-----------|
	
    set_overlay_input_axial_50band1 ---------------------------> Set overlay for 50% band in row 1, in axial plane ------------|
	set_overlay_input_sagittal_50band1 ------------------------> Set overlay for 50% band in row 1, in sagittal plane          |  overlay_ipws_50band1, overlay_active_50band1
	set_overlay_input_coronal_50band1	------------------------> Set overlay for 50% band in row 1, in coronal plane-----------|
	
	--------------------------------------------------------------------------------------------------------------------------------------------------------------
	
	set_overlay_input_axial_100band2 ---------------------------> Set overlay for 100% band in row 2, in axial plane ------------|
	set_overlay_input_sagittal_100band2 ------------------------> Set overlay for 100% band in row 2, in sagittal plane          |  overlay_ipws_100band2, overlay_active_100band2
	set_overlay_input_coronal_100band2	------------------------> Set overlay for 100% band in row 2, in coronal plane-----------|
	
	set_overlay_input_axial_50band2 ---------------------------> Set overlay for 50% band in row 2, in axial plane ------------|
	set_overlay_input_sagittal_50band2 ------------------------> Set overlay for 50% band in row 2, in sagittal plane          |  overlay_ipws_50band2, overlay_active_50band2
	set_overlay_input_coronal_50band2	------------------------> Set overlay for 50% band in row 2, in coronal plane-----------|
	
	---------------------------------------------------------------------------------------------------------------------------------------------------------------
	
	set_overlay_input_axial_100band3 ---------------------------> Set overlay for 100% band in row 3, in axial plane ------------|
	set_overlay_input_sagittal_100band3 ------------------------> Set overlay for 100% band in row 3, in sagittal plane          |  overlay_ipws_100band3, overlay_active_100band3
	set_overlay_input_coronal_100band3	------------------------> Set overlay for 100% band in row 3, in coronal plane-----------|
	
	set_overlay_input_axial_50band3 ---------------------------> Set overlay for 50% band in row 3, in axial plane ------------|
	set_overlay_input_sagittal_50band3 ------------------------> Set overlay for 50% band in row 3, in sagittal plane          |  overlay_ipws_100band3, overlay_active_100band3
	set_overlay_input_coronal_50band3	------------------------> Set overlay for 50% band in row 3, in coronal plane-----------|
	
	'''
		
	###------------------------FIRST ROW---------------------------###
		
    def set_overlay_input_axial_100band1(self, input):
        self.overlay_active_100band1 = 1
        ipw = self.overlay_ipws_100band1[0]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_100band1 = 0;
            for ipw_overlay in self.overlay_ipws_100band1:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [1, 0, 0]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_100band1):
                self.observer_sync_overlay(self.ipws, i)        
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # axial
                ipw_overlay.SetEnabled(active[i]) 
        self.render()
		

    def set_overlay_input_sagittal_100band1(self, input):
        self.overlay_active_100band1 = 1
        ipw = self.overlay_ipws_100band1[1]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_100band1 = 0;
            for ipw_overlay in self.overlay_ipws_100band1:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [0, 1, 0]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_100band1):
                self.observer_sync_overlay(self.ipws, i)
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # sagittal
                ipw_overlay.SetEnabled(active[i])
        self.render()


    def set_overlay_input_coronal_100band1(self, input):
        self.overlay_active_100band1 = 1
        ipw = self.overlay_ipws_100band1[2]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_100band1 = 0;
            for ipw_overlay in self.overlay_ipws_100band1:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [0, 0, 1]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_100band1):
                self.observer_sync_overlay(self.ipws, i)
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # coronal
                ipw_overlay.SetEnabled(active[i])
        self.render()		
		
		
    def set_overlay_input_axial_50band1(self, input):
        self.overlay_active_50band1 = 1
        ipw = self.overlay_ipws_50band1[0]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_50band1 = 0;
            for ipw_overlay in self.overlay_ipws_50band1:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [1, 0, 0]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_50band1):
                self.observer_sync_overlay(self.ipws, i)        
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # axial
                ipw_overlay.SetEnabled(active[i]) 
        self.render()
		

    def set_overlay_input_sagittal_50band1(self, input):
        self.overlay_active_50band1 = 1
        ipw = self.overlay_ipws_50band1[1]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_50band1 = 0;
            for ipw_overlay in self.overlay_ipws_50band1:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [0, 1, 0]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_50band1):
                self.observer_sync_overlay(self.ipws, i)
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # sagittal
                ipw_overlay.SetEnabled(active[i])
        self.render()


    def set_overlay_input_coronal_50band1(self, input):
        self.overlay_active_50band1 = 1
        ipw = self.overlay_ipws_50band1[2]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_50band1 = 0;
            for ipw_overlay in self.overlay_ipws_50band1:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [0, 0, 1]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_50band1):
                self.observer_sync_overlay(self.ipws, i)
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # coronal
                ipw_overlay.SetEnabled(active[i])
        self.render()
		
	###------------------------SECOND ROW---------------------------###
		
    def set_overlay_input_axial_100band2(self, input):
        self.overlay_active_100band2 = 1
        ipw = self.overlay_ipws_100band2[0]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_100band2 = 0;
            for ipw_overlay in self.overlay_ipws_100band2:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [1, 0, 0]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_100band2):
                self.observer_sync_overlay(self.ipws, i)        
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # axial
                ipw_overlay.SetEnabled(active[i]) 
        self.render()
		

    def set_overlay_input_sagittal_100band2(self, input):
        self.overlay_active_100band2 = 1
        ipw = self.overlay_ipws_100band2[1]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_100band2 = 0;
            for ipw_overlay in self.overlay_ipws_100band2:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [0, 1, 0]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_100band2):
                self.observer_sync_overlay(self.ipws, i)
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # sagittal
                ipw_overlay.SetEnabled(active[i])
        self.render()


    def set_overlay_input_coronal_100band2(self, input):
        self.overlay_active_100band2 = 1
        ipw = self.overlay_ipws_100band2[2]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_100band2 = 0;
            for ipw_overlay in self.overlay_ipws_100band2:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [0, 0, 1]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_100band2):
                self.observer_sync_overlay(self.ipws, i)
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # coronal
                ipw_overlay.SetEnabled(active[i])
        self.render()
		
		
    def set_overlay_input_axial_50band2(self, input):
        self.overlay_active_50band2 = 1
        ipw = self.overlay_ipws_50band2[0]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_50band2 = 0;
            for ipw_overlay in self.overlay_ipws_50band2:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [1, 0, 0]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_50band2):
                self.observer_sync_overlay(self.ipws, i)        
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # axial
                ipw_overlay.SetEnabled(active[i]) 
        self.render()
		

    def set_overlay_input_sagittal_50band2(self, input):
        self.overlay_active_50band2 = 1
        ipw = self.overlay_ipws_50band2[1]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_50band2 = 0;
            for ipw_overlay in self.overlay_ipws_50band2:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [0, 1, 0]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_50band2):
                self.observer_sync_overlay(self.ipws, i)
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # sagittal
                ipw_overlay.SetEnabled(active[i])
        self.render()


    def set_overlay_input_coronal_50band2(self, input):
        self.overlay_active_50band2 = 1
        ipw = self.overlay_ipws_50band2[2]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_50band2 = 0;
            for ipw_overlay in self.overlay_ipws_50band2:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [0, 0, 1]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_50band2):
                self.observer_sync_overlay(self.ipws, i)
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # coronal
                ipw_overlay.SetEnabled(active[i])
        self.render()
		
	###-------------------------THIRD ROW---------------------------###
	
	
    def set_overlay_input_axial_100band3(self, input):
        self.overlay_active_100band3 = 1
        ipw = self.overlay_ipws_100band3[0]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_100band3 = 0;
            for ipw_overlay in self.overlay_ipws_100band3:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [1, 0, 0]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_100band3):
                self.observer_sync_overlay(self.ipws, i)        
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # axial
                ipw_overlay.SetEnabled(active[i]) 
        self.render()
		

    def set_overlay_input_sagittal_100band3(self, input):
        self.overlay_active_100band3 = 1
        ipw = self.overlay_ipws_100band3[1]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_100band3 = 0;
            for ipw_overlay in self.overlay_ipws_100band3:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [0, 1, 0]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_100band3):
                self.observer_sync_overlay(self.ipws, i)
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # sagittal
                ipw_overlay.SetEnabled(active[i])
        self.render()


    def set_overlay_input_coronal_100band3(self, input):
        self.overlay_active_100band3 = 1
        ipw = self.overlay_ipws_100band3[2]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_100band3 = 0;
            for ipw_overlay in self.overlay_ipws_100band3:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [0, 0, 1]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_100band3):
                self.observer_sync_overlay(self.ipws, i)
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # coronal
                ipw_overlay.SetEnabled(active[i])
        self.render()
		
    def set_overlay_input_axial_50band3(self, input):
        self.overlay_active_50band3 = 1
        ipw = self.overlay_ipws_50band3[0]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_50band3 = 0;
            for ipw_overlay in self.overlay_ipws_50band3:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [1, 0, 0]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_50band3):
                self.observer_sync_overlay(self.ipws, i)        
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # axial
                ipw_overlay.SetEnabled(active[i]) 
        self.render()
		

    def set_overlay_input_sagittal_50band3(self, input):
        self.overlay_active_50band3 = 1
        ipw = self.overlay_ipws_50band3[1]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_50band1 = 0;
            for ipw_overlay in self.overlay_ipws_50band3:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [0, 1, 0]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_50band3):
                self.observer_sync_overlay(self.ipws, i)
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # sagittal
                ipw_overlay.SetEnabled(active[i])
        self.render()


    def set_overlay_input_coronal_50band3(self, input):
        self.overlay_active_50band3 = 1
        ipw = self.overlay_ipws_50band3[2]
        if input == ipw.GetInput():
            return
        if input is None:
            self.overlay_active_50band3 = 0;
            for ipw_overlay in self.overlay_ipws_50band3:
                ipw_overlay.SetEnabled(0)
                ipw_overlay.SetInput(None)
        else:
            active = [0, 0, 1]
            orientations = [2, 0, 1]
            for i, ipw_overlay in enumerate(self.overlay_ipws_50band3):
                self.observer_sync_overlay(self.ipws, i)
                ipw_overlay.SetInput(input)
                ipw_overlay.SetPlaneOrientation(orientations[i]) # coronal
                ipw_overlay.SetEnabled(active[i])
        self.render()
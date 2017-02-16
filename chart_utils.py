# Copyright (c) Pedro Silva, TU Eindhoven.
# All rights reserved.
# See COPYRIGHT for details.
# ---------------------------------------

# Highlight rectangle from bar plot with the animation blit techniques.
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

class HighlightableRectangle:

    lock = None  # only one can be animated at a time
    def __init__(self, rect):
        self.rect = rect
        self.press = None
        self.background = None
        #self.annotation = self.setup_annotation()
        #self.annotation.set_text("Hello")

    def connect(self):
        'connect to all the events we need'
        self.cidpress = self.rect.figure.canvas.mpl_connect(
            'button_press_event', self.on_press)
        self.cidrelease = self.rect.figure.canvas.mpl_connect(
            'button_release_event', self.on_release)
        self.cidmotion = self.rect.figure.canvas.mpl_connect(
            'motion_notify_event', self.on_movement)
        
        '''self.pick = self.rect.figure.canvas.mpl_connect(
            'pick_event', self.on_pick)'''
        
        #self.highlight = self.rect.figure.canvas.mpl_connect("motion_notify_event",fig.canvas.onHilite)
        
    def setup_annotation(self):
        """Draw and hide the annotation box."""
        annotation = self.rect.axes.annotate(
            '', xy=(0, 0), ha = 'right',
            xytext = (-5,5), textcoords = 'offset points', va = 'bottom',
            bbox = dict(
                boxstyle='round,pad=0.5', fc='yellow', alpha=0.75),
            arrowprops = dict(
                arrowstyle='->', connectionstyle='arc3,rad=0'))
        return annotation
        
    def on_movement(self,event):
        if event.inaxes != self.rect.axes:
            return
        if HighlightableRectangle.lock is not None: 
            return
        contains, attrd = self.rect.contains(event)
        if contains: 
            self.rect.set_facecolor('red')
            print 'event contains', str(self.rect.xy[0] + 70)
            #self.annotation.set_visible(True) 
        else:            
            self.rect.set_facecolor('blue')
            #self.annotation.set_visible(False) 
            
        #print(self.rect.get_facecolor())
        axes = self.rect.axes
        self.rect.set_animated(True)
        # now redraw just the rectangle
        canvas = self.rect.figure.canvas
        axes.draw_artist(self.rect)
        canvas.blit(axes.bbox)
            
        #self.rect.figure.canvas.draw()
        #print 'event contains', str(self.rect.xy[0] + 70)

    def on_press(self, event):
        'on button press we will see if the mouse is over us and store some data'
        if event.inaxes != self.rect.axes: return
        if HighlightableRectangle.lock is not None: return
        contains, attrd = self.rect.contains(event)
        if not contains: return
        print 'event contains', str(self.rect.xy[0] + 70)
        x0, y0 = self.rect.xy
        self.press = x0, y0, event.xdata, event.ydata
        
        
        
        self.pressed = True
        self.rect.set_facecolor('red')
        
        HighlightableRectangle.lock = self

        # draw everything but the selected rectangle and store the pixel buffer
        canvas = self.rect.figure.canvas
        axes = self.rect.axes
        self.rect.set_animated(True)
        canvas.draw()
        self.background = canvas.copy_from_bbox(self.rect.axes.bbox)

        # now redraw just the rectangle
        axes.draw_artist(self.rect)

        # and blit just the redrawn area
        canvas.blit(axes.bbox)

    def on_motion(self, event):
        'on motion we will move the rect if the mouse is over us'
        if HighlightableRectangle.lock is not self:
            return
        if event.inaxes != self.rect.axes: return
        x0, y0, xpress, ypress = self.press
        dx = event.xdata - xpress
        dy = event.ydata - ypress
        self.rect.set_x(x0+dx)
        self.rect.set_y(y0+dy)

        canvas = self.rect.figure.canvas
        axes = self.rect.axes
        # restore the background region
        canvas.restore_region(self.background)

        # redraw just the current rectangle
        axes.draw_artist(self.rect)

        # blit just the redrawn area
        canvas.blit(axes.bbox)

    def on_release(self, event):
        'on release we reset the press data'
        if HighlightableRectangle.lock is not self:
            return

        self.press = None
        HighlightableRectangle.lock = None

        # turn off the rect animation property and reset the background
        self.rect.set_animated(False)
        self.background = None

        # redraw the full figure
        self.rect.figure.canvas.draw()

    def disconnect(self):
        'disconnect all the stored connection ids'
        self.rect.figure.canvas.mpl_disconnect(self.cidpress)
        self.rect.figure.canvas.mpl_disconnect(self.cidrelease)
        self.rect.figure.canvas.mpl_disconnect(self.cidmotion)
			

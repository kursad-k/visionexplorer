import tkinter as tk
from PIL import Image, ImageTk, ImageGrab
import tempfile
import os

class ScreenSelector:
    def __init__(self):
        self.start_x = None
        self.start_y = None
        self.end_x = None
        self.end_y = None
        self.rect = None
        self.root = None
        self.canvas = None
        
    def capture_area(self):
        """Capture selected screen area and return image path"""
        # Take full screenshot first
        screenshot = ImageGrab.grab()
        
        # Get screen dimensions
        screen_width = screenshot.width
        screen_height = screenshot.height
        
        # Create fullscreen overlay for selection
        self.root = tk.Tk()
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-alpha', 0.3)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='black')
        
        # Create canvas without background image
        self.canvas = tk.Canvas(self.root, highlightthickness=0, bg='gray')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Store screenshot and screen dimensions
        self.screenshot = screenshot
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        # Bind mouse events and ESC key - multiple bindings for reliability
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", lambda e: self.cancel_selection())  # Right click cancels
        
        # Multiple ESC key bindings
        self.root.bind('<Escape>', lambda e: self.cancel_selection())
        self.root.bind('<KeyPress-Escape>', lambda e: self.cancel_selection())
        self.canvas.bind('<Escape>', lambda e: self.cancel_selection())
        self.canvas.bind('<KeyPress-Escape>', lambda e: self.cancel_selection())
        self.canvas.bind('<Key>', lambda e: self.on_any_key(e))
        
        # Set focus and make sure window can receive key events
        self.root.focus_force()
        self.canvas.focus_set()
        self.root.grab_set()
        
        # Instructions
        instruction = tk.Label(self.root, text="Click and drag to select area. Press ESC to cancel.", 
                             fg='white', bg='black', font=('Arial', 12))
        instruction.pack(pady=10)
        
        self.root.mainloop()
        
        if self.start_x is not None and self.end_x is not None:
            # Scale coordinates from canvas to screen
            scale_x = self.screen_width / self.canvas_width
            scale_y = self.screen_height / self.canvas_height
            
            left = int(min(self.start_x, self.end_x) * scale_x)
            top = int(min(self.start_y, self.end_y) * scale_y)
            right = int(max(self.start_x, self.end_x) * scale_x)
            bottom = int(max(self.start_y, self.end_y) * scale_y)
            
            cropped = self.screenshot.crop((left, top, right, bottom))
            
            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            cropped.save(temp_file.name)
            return temp_file.name
        
        return None
    
    def on_click(self, event):
        self.start_x = event.x
        self.start_y = event.y
        
    def on_drag(self, event):
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, event.x, event.y,
            outline='red', width=2
        )
        
    def on_release(self, event):
        self.end_x = event.x
        self.end_y = event.y
        # Get canvas dimensions before destroying
        self.canvas_width = self.canvas.winfo_width()
        self.canvas_height = self.canvas.winfo_height()
        self.root.quit()
        self.root.destroy()
        

    
    def on_any_key(self, event):
        if event.keysym == 'Escape':
            self.cancel_selection()
    
    def cancel_selection(self):
        self.start_x = None
        self.end_x = None
        self.root.quit()
        self.root.destroy()
        # Exit the entire application
        import sys
        sys.exit()
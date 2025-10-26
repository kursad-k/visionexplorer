import os
import threading
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.text import LabelBase
from screen_capture import ScreenSelector
from text_extractor_twopass import extract_text_from_image_twopass as extract_text_from_image

# Register a font that supports Unicode characters
try:
    LabelBase.register(name='DejaVuSans', fn_regular='DejaVuSans.ttf')
except:
    pass  # Use default font if DejaVu not available

class ScreenExplorerApp(App):
    def build(self):
        Window.hide()
        Window.clearcolor = (0.1, 0.1, 0.1, 1)  # Dark background
        Window.size = (int(Window.size[0] * 1.5), Window.size[1])  # Make window 1.5x wider
        
        main_layout = BoxLayout(
            orientation='vertical', 
            padding=10, 
            spacing=10
        )
        
        # Three-column layout: Image, Text, Visual
        content_layout = BoxLayout(orientation='horizontal', spacing=10)
        
        # Image display area
        image_layout = BoxLayout(orientation='vertical', spacing=5)
        self.image_label = Label(
            text='Captured Image:', 
            size_hint_y=None, 
            height=30, 
            halign='left',
            color=(0.9, 0.9, 0.9, 1)
        )
        self.image_label.bind(size=self.image_label.setter('text_size'))
        image_layout.add_widget(self.image_label)
        
        self.image_display = Image(
            source='',
            allow_stretch=True,
            keep_ratio=True
        )
        image_layout.add_widget(self.image_display)
        
        # Text content area
        text_layout = BoxLayout(orientation='vertical', spacing=5)
        text_label = Label(
            text='Extracted Text:', 
            size_hint_y=None, 
            height=30, 
            halign='left',
            color=(0.9, 0.9, 0.9, 1)
        )
        text_label.bind(size=text_label.setter('text_size'))
        text_layout.add_widget(text_label)
        
        self.text_area = TextInput(
            text='Starting capture...',
            multiline=True,
            readonly=True,
            background_color=(0.2, 0.2, 0.2, 1),
            foreground_color=(0.9, 0.9, 0.9, 1),
            font_name='RobotoMono-Regular',
            font_size='14sp'
        )
        text_layout.add_widget(self.text_area)
        
        # Visual content area
        visual_layout = BoxLayout(orientation='vertical', spacing=5)
        visual_label = Label(
            text='Visual Description:', 
            size_hint_y=None, 
            height=30, 
            halign='left',
            color=(0.9, 0.9, 0.9, 1)
        )
        visual_label.bind(size=visual_label.setter('text_size'))
        visual_layout.add_widget(visual_label)
        
        self.visual_area = TextInput(
            text='',
            multiline=True,
            readonly=True,
            background_color=(0.2, 0.2, 0.2, 1),
            foreground_color=(0.9, 0.9, 0.9, 1),
            font_name='RobotoMono-Regular',
            font_size='14sp'
        )
        visual_layout.add_widget(self.visual_area)
        
        content_layout.add_widget(image_layout)
        content_layout.add_widget(text_layout)
        content_layout.add_widget(visual_layout)
        main_layout.add_widget(content_layout)
        
        # Capture button
        capture_btn = Button(
            text='Capture Screen Area',
            size_hint_y=None,
            height=50,
            background_color=(0.3, 0.3, 0.3, 1),  # Dark button
            color=(0.9, 0.9, 0.9, 1)  # Light text
        )
        capture_btn.bind(on_press=self.capture_screen)
        main_layout.add_widget(capture_btn)
        
        Clock.schedule_once(self.initial_capture, 0.5)
        
        return main_layout
    
    def initial_capture(self, dt):
        self.capture_screen(None)
    
    def capture_screen(self, instance):
        Window.hide()
        
        try:
            selector = ScreenSelector()
            image_path = selector.capture_area()
            
            if image_path:
                # Show image immediately
                self.image_display.source = image_path
                self.image_label.text = 'Captured Image: Processing...'
                self.text_area.text = 'Processing with Ollama...'
                self.visual_area.text = ''
                Window.show()
                
                # Process in background thread
                thread = threading.Thread(target=self.process_image, args=(image_path,))
                thread.daemon = False  # Don't kill thread when main exits
                thread.start()
            else:
                self.text_area.text = 'Capture cancelled'
                self.visual_area.text = ''
                Window.show()
        
        except Exception as e:
            self.text_area.text = f'Capture error: {str(e)}'
            self.visual_area.text = ''
            Window.show()
    
    def process_image(self, image_path):
        """Process image in background thread"""
        try:
            print("Starting Ollama processing...")
            
            # Get original and processed dimensions
            from PIL import Image as PILImage
            with PILImage.open(image_path) as img:
                orig_w, orig_h = img.size
            
            # Get processed image path to check final dimensions
            from text_extractor_twopass import resize_image_if_needed
            proc_path = resize_image_if_needed(image_path)
            
            with PILImage.open(proc_path) as img:
                proc_w, proc_h = img.size
            
            # Update label with both dimensions
            if proc_path != image_path:
                Clock.schedule_once(lambda dt: setattr(self.image_label, 'text', f'Captured Image: {orig_w}x{orig_h} → {proc_w}x{proc_h} (resized)'))
            else:
                Clock.schedule_once(lambda dt: setattr(self.image_label, 'text', f'Captured Image: {orig_w}x{orig_h}'))
            
            text_content, visual_content, _ = extract_text_from_image(image_path)
            print("Ollama processing completed")
            # Update UI from main thread
            Clock.schedule_once(lambda dt: self.update_results(image_path, text_content, visual_content))
        except Exception as e:
            print(f"Error in process_image: {str(e)}")
            Clock.schedule_once(lambda dt: self.update_results(image_path, f'Error: {str(e)}', f'Processing failed: {str(e)}'))
        # Don't delete image file yet - display it first
    
    def update_results(self, image_path, text_content, visual_content):
        """Update UI with results (called from main thread)"""
        # Image already displayed, just update text areas
        self.text_area.text = text_content
        self.visual_area.text = visual_content
        
        # Clean up temp file after displaying
        Clock.schedule_once(lambda dt: self.cleanup_image(image_path), 2)
    
    def cleanup_image(self, image_path):
        """Clean up temporary image file"""
        try:
            os.unlink(image_path)
        except:
            pass

if __name__ == '__main__':
    try:
        ScreenExplorerApp().run()
    except Exception as e:
        print(f"App error: {e}")
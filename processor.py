import os
import uuid
from PIL import Image, ImageDraw, ImageFont, ImageOps
import arabic_reshaper
from bidi.algorithm import get_display

# پیکربندی اختصاصی برای زبان فارسی
reshaper_config = {
    'delete_harakat': False,
    'support_ligatures': True,
    'use_unshaped_instead_of_isolated': True,
}
reshaper = arabic_reshaper.ArabicReshaper(reshaper_config)

class StoryProcessor:
    def __init__(self, template_text_path, template_image_path, font_path):
        self.template_text_path = template_text_path
        self.template_image_path = template_image_path
        self.font_path = font_path
        
        self.output_dir = os.path.join('static', 'outputs')
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.story_size = (1080, 1920)
        
        # --- تنظیمات قالب ۱: فقط متن (کادر مرمر) ---
        self.text_only_max_width = 720 
        self.marble_usable_start_y = 360 
        self.marble_usable_end_y = 1580  
        self.text_only_color = (30, 30, 30)
        
        # --- تنظیمات قالب ۲: متن و عکس (کرم‌رنگ) ---
        self.with_img_max_width = 720 
        self.image_box_size = (800, 600) 
        self.image_box_position = (140, 430) 
        self.with_img_start_y = 1060 
        self.with_img_end_y = 1440   
        self.with_img_color = (30, 30, 30)

    def _prepare_persian_text(self, text, body_font, header_font, max_width):
        lines = []
        paragraphs = text.replace('\r', '').split('\n')
        
        for i, paragraph in enumerate(paragraphs):
            paragraph = paragraph.strip()
            is_header = (i == 0)
            current_font = header_font if is_header else body_font
            
            if not paragraph:
                lines.append({'text': '', 'is_header': False, 'is_empty': True})
                continue
                
            words = paragraph.split()
            current_line = []
            
            for word in words:
                current_line.append(word)
                test_line = ' '.join(current_line)
                
                # تبدیل و راست‌چین کردن
                reshaped = reshaper.reshape(test_line)
                bidi_text = get_display(reshaped)
                
                width = current_font.getlength(bidi_text)
                        
                if width > max_width:
                    if len(current_line) == 1:
                        reshaped = reshaper.reshape(current_line[0])
                        lines.append({'text': get_display(reshaped), 'is_header': is_header, 'is_empty': False})
                        current_line = []
                    else:
                        current_line.pop()
                        reshaped_final = reshaper.reshape(' '.join(current_line))
                        lines.append({'text': get_display(reshaped_final), 'is_header': is_header, 'is_empty': False})
                        current_line = [word]
                        
            if current_line:
                reshaped_final = reshaper.reshape(' '.join(current_line))
                lines.append({'text': get_display(reshaped_final), 'is_header': is_header, 'is_empty': False})
                
            if lines and not lines[-1].get('is_empty'):
                lines[-1]['is_paragraph_end'] = True
                
        return lines

    def _get_dynamic_font(self, text, start_font_size, max_width, max_height):
        low = 20
        high = start_font_size
        
        best_font_size = 20
        best_header_size = 35
        best_body_font = None
        best_header_font = None
        best_line_spacing = 0
        best_paragraph_spacing = 0
        best_lines = []

        while low <= high:
            mid_font_size = (low + high) // 2
            header_font_size = mid_font_size + 15
            
            try:
                # خنثی کردن موتور لینوکس با LAYOUT_BASIC
                if hasattr(ImageFont, 'LAYOUT_BASIC'):
                    body_font = ImageFont.truetype(self.font_path, mid_font_size, layout_engine=ImageFont.LAYOUT_BASIC)
                    header_font = ImageFont.truetype(self.font_path, header_font_size, layout_engine=ImageFont.LAYOUT_BASIC)
                else:
                    body_font = ImageFont.truetype(self.font_path, mid_font_size)
                    header_font = ImageFont.truetype(self.font_path, header_font_size)
            except IOError:
                body_font = ImageFont.load_default()
                header_font = ImageFont.load_default()
                
            line_spacing = int(mid_font_size * 0.4)
            paragraph_spacing = int(mid_font_size * 0.8)
            
            lines = self._prepare_persian_text(text, body_font, header_font, max_width)
            
            total_height = 0
            for line in lines:
                if line.get('is_empty'):
                    total_height += mid_font_size + line_spacing
                else:
                    current_size = header_font_size if line['is_header'] else mid_font_size
                    total_height += current_size + line_spacing
                    if line.get('is_paragraph_end'):
                        total_height += paragraph_spacing
            
            if total_height <= max_height:
                best_font_size = mid_font_size
                best_header_size = header_font_size
                best_body_font = body_font
                best_header_font = header_font
                best_line_spacing = line_spacing
                best_paragraph_spacing = paragraph_spacing
                best_lines = lines
                
                low = mid_font_size + 1 
            else:
                high = mid_font_size - 1
                
        if best_body_font is None:
            best_font_size = 20
            best_header_size = 35
            try:
                if hasattr(ImageFont, 'LAYOUT_BASIC'):
                    best_body_font = ImageFont.truetype(self.font_path, 20, layout_engine=ImageFont.LAYOUT_BASIC)
                    best_header_font = ImageFont.truetype(self.font_path, 35, layout_engine=ImageFont.LAYOUT_BASIC)
                else:
                    best_body_font = ImageFont.truetype(self.font_path, 20)
                    best_header_font = ImageFont.truetype(self.font_path, 35)
            except IOError:
                best_body_font = ImageFont.load_default()
                best_header_font = ImageFont.load_default()
            best_line_spacing = int(20 * 0.4)
            best_paragraph_spacing = int(20 * 0.8)
            best_lines = self._prepare_persian_text(text, best_body_font, best_header_font, max_width)

        return best_body_font, best_header_font, best_font_size, best_header_size, best_line_spacing, best_paragraph_spacing, best_lines

    def generate_story(self, mode, text, image_stream=None):
        selected_template = self.template_text_path if mode == 'text_only' else self.template_image_path
        base_img = Image.open(selected_template).convert("RGBA")
        base_img = base_img.resize(self.story_size)
        draw = ImageDraw.Draw(base_img)

        if mode == 'text_only':
            current_max_width = self.text_only_max_width
            text_color = self.text_only_color
            usable_height = self.marble_usable_end_y - self.marble_usable_start_y
            
            body_font, header_font, final_size, header_size, line_spacing, para_spacing, lines = self._get_dynamic_font(
                text, start_font_size=55, max_width=current_max_width, max_height=usable_height
            )
            
            total_text_height = 0
            for line in lines:
                if line.get('is_empty'):
                    total_text_height += final_size + line_spacing
                else:
                    current_size = header_size if line['is_header'] else final_size
                    total_text_height += current_size + line_spacing
                    if line.get('is_paragraph_end'):
                        total_text_height += para_spacing
                        
            offset = max(0, (usable_height - total_text_height) // 2)
            current_y = self.marble_usable_start_y + offset

        else:
            current_max_width = self.with_img_max_width
            text_color = self.with_img_color
            usable_height = self.with_img_end_y - self.with_img_start_y
            
            if image_stream:
                user_img = Image.open(image_stream).convert("RGBA")
                user_img = ImageOps.fit(user_img, self.image_box_size, Image.Resampling.LANCZOS)
                base_img.paste(user_img, self.image_box_position, user_img)
                
            body_font, header_font, final_size, header_size, line_spacing, para_spacing, lines = self._get_dynamic_font(
                text, start_font_size=45, max_width=current_max_width, max_height=usable_height
            )
            
            total_text_height = 0
            for line in lines:
                if line.get('is_empty'):
                    total_text_height += final_size + line_spacing
                else:
                    current_size = header_size if line['is_header'] else final_size
                    total_text_height += current_size + line_spacing
                    if line.get('is_paragraph_end'):
                        total_text_height += para_spacing
                        
            offset = max(0, (usable_height - total_text_height) // 2)
            current_y = self.with_img_start_y + offset

        for line in lines:
            if line.get('is_empty'):
                current_y += final_size + line_spacing
                continue
                
            current_font = header_font if line['is_header'] else body_font
            current_size = header_size if line['is_header'] else final_size
            
            color = (18, 76, 84) if line['is_header'] else text_color
                
            line_width = current_font.getlength(line['text'])
            
            right_margin = (self.story_size[0] - current_max_width) / 2
            x_pos = self.story_size[0] - right_margin - line_width
            
            # رسم متن نهایی کاملاً ساده
            draw.text((x_pos, current_y), line['text'], font=current_font, fill=color)
            
            current_y += current_size + line_spacing
            
            if line.get('is_paragraph_end'):
                current_y += para_spacing

        final_img = base_img.convert("RGB")
        filename = f"story_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join(self.output_dir, filename)
        final_img.save(filepath, quality=95)
        
        return filename

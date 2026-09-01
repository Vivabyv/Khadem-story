import os
import uuid
from PIL import Image, ImageDraw, ImageFont, ImageOps
import arabic_reshaper
from bidi.algorithm import get_display

# تشخیص هوشمند موتور رندر لینوکس
try:
    from PIL import features
    HAS_RAQM = features.check('raqm')
except ImportError:
    HAS_RAQM = False

class StoryProcessor:
    def __init__(self, template_text_path, template_image_path, font_path):
        self.template_text_path = template_text_path
        self.template_image_path = template_image_path
        self.font_path = font_path
        
        self.output_dir = os.path.join('static', 'outputs')
        os.makedirs(self.output_dir, exist_ok=True)
        self.story_size = (1080, 1920)
        
        # --- هارمونی رنگ‌ها ---
        self.color_bg = (255, 255, 255, 255)      
        self.color_gold = (212, 168, 83, 255)     
        self.color_teal = (12, 100, 115, 255)     
        self.color_text = (50, 50, 50, 255)       
        
        # --- تنظیمات قالب ۱: فقط متن (قالب آماده مرمرین) ---
        self.text_only_max_width = 760 
        self.marble_usable_start_y = 400 
        self.marble_usable_end_y = 1500  
        self.text_only_color = (30, 30, 30)

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
                
                if HAS_RAQM:
                    width = current_font.getlength(test_line, direction='rtl')
                else:
                    width = current_font.getlength(get_display(arabic_reshaper.reshape(test_line)))
                        
                if width > max_width:
                    if len(current_line) == 1:
                        lines.append({'text': current_line[0], 'is_header': is_header, 'is_empty': False})
                        current_line = []
                    else:
                        current_line.pop()
                        lines.append({'text': ' '.join(current_line), 'is_header': is_header, 'is_empty': False})
                        current_line = [word]
                        
            if current_line:
                lines.append({'text': ' '.join(current_line), 'is_header': is_header, 'is_empty': False})
                
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
        best_total_height = 0

        while low <= high:
            mid_font_size = (low + high) // 2
            header_font_size = mid_font_size + 15
            
            try:
                if hasattr(ImageFont, 'LAYOUT_BASIC'):
                    body_font = ImageFont.truetype(self.font_path, mid_font_size, layout_engine=ImageFont.LAYOUT_BASIC)
                    header_font = ImageFont.truetype(self.font_path, header_font_size, layout_engine=ImageFont.LAYOUT_BASIC)
                else:
                    body_font = ImageFont.truetype(self.font_path, mid_font_size)
                    header_font = ImageFont.truetype(self.font_path, header_font_size)
            except IOError:
                body_font = ImageFont.load_default()
                header_font = ImageFont.load_default()
                
            line_spacing = int(mid_font_size * 0.5)
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
                best_total_height = total_height
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
                pass
            best_line_spacing = int(20 * 0.5)
            best_paragraph_spacing = int(20 * 0.8)
            best_lines = self._prepare_persian_text(text, best_body_font, best_header_font, max_width)
            best_total_height = 0
            for line in best_lines:
                current_size = best_header_size if line.get('is_header', False) else best_font_size
                best_total_height += current_size + best_line_spacing
                if line.get('is_paragraph_end', False):
                    best_total_height += best_paragraph_spacing

        return best_body_font, best_header_font, best_font_size, best_header_size, best_line_spacing, best_paragraph_spacing, best_lines, best_total_height

    def generate_story(self, mode, text, image_stream=None):
        if mode == 'text_only':
            # --- پردازش حالت اول: فقط متن (بدون کادر داینامیک، روی قالب مرمرین) ---
            base_img = Image.open(self.template_text_path).convert("RGBA")
            base_img = base_img.resize(self.story_size)
            draw = ImageDraw.Draw(base_img)
            
            current_max_width = self.text_only_max_width
            usable_height = self.marble_usable_end_y - self.marble_usable_start_y
            
            body_font, header_font, final_size, header_size, line_spacing, para_spacing, lines, text_height = self._get_dynamic_font(
                text, start_font_size=55, max_width=current_max_width, max_height=usable_height
            )
            
            # تراز عمودی متن روی قالب ثابت
            offset = max(0, (usable_height - text_height) // 2)
            current_y = self.marble_usable_start_y + offset

            for line in lines:
                if line.get('is_empty'):
                    current_y += final_size + line_spacing
                    continue
                current_font = header_font if line['is_header'] else body_font
                current_size = header_size if line['is_header'] else final_size
                color = self.color_teal if line['is_header'] else self.text_only_color
                
                if HAS_RAQM:
                    line_width = current_font.getlength(line['text'], direction='rtl')
                    right_margin = (self.story_size[0] - current_max_width) / 2
                    x_pos = self.story_size[0] - right_margin - line_width
                    draw.text((x_pos, current_y), line['text'], font=current_font, fill=color, direction='rtl')
                else:
                    shaped_text = get_display(arabic_reshaper.reshape(line['text']))
                    line_width = current_font.getlength(shaped_text)
                    right_margin = (self.story_size[0] - current_max_width) / 2
                    x_pos = self.story_size[0] - right_margin - line_width
                    draw.text((x_pos, current_y), shaped_text, font=current_font, fill=color)
                
                current_y += current_size + line_spacing
                if line.get('is_paragraph_end'):
                    current_y += para_spacing

        else:
            # --- پردازش حالت دوم: متن و عکس (کادر هوشمند داینامیک) ---
            # 1. ساخت بوم کاملا سفید
            base_img = Image.new("RGBA", self.story_size, self.color_bg)
            draw = ImageDraw.Draw(base_img)

            # 2. قرار دادن لوگو (از روی فایل template_image.jpg که الان لوگو است)
            logo_path = self.template_image_path
            available_start_y = 350
            
            if os.path.exists(logo_path):
                logo_img = Image.open(logo_path).convert("RGBA")
                target_width = 260 # سایز لوگو مینیمال و شیک
                w_percent = (target_width / float(logo_img.size[0]))
                target_height = int((float(logo_img.size[1]) * float(w_percent)))
                
                logo_resized = logo_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                logo_x = (self.story_size[0] - target_width) // 2
                logo_y = 80 # چسباندن لوگو به بالای صفحه
                
                # قرار دادن لوگو روی بوم
                try:
                    base_img.paste(logo_resized, (logo_x, logo_y), logo_resized)
                except ValueError:
                    base_img.paste(logo_resized, (logo_x, logo_y))
                
                available_start_y = logo_y + target_height + 60 
                
            # 3. محاسبات کادر داینامیک
            margin_x = 80  
            box_width = self.story_size[0] - (margin_x * 2) 
            inner_padding = 60 
            content_max_width = box_width - (inner_padding * 2) 
            
            available_end_y = 1840 
            available_height = available_end_y - available_start_y
            
            content_height = 0
            img_h = 0
            user_img_resized = None
            
            # 4. پردازش عکس کاربر
            if image_stream:
                user_img = Image.open(image_stream).convert("RGB")
                img_w = content_max_width 
                img_h = int((float(user_img.size[1]) * float(img_w / float(user_img.size[0]))))
                
                if img_h > 480:
                    img_h = 480
                    img_w = int((float(user_img.size[0]) * float(img_h / float(user_img.size[1]))))
                
                user_img_resized = ImageOps.fit(user_img, (img_w, img_h), Image.Resampling.LANCZOS)
                content_height += img_h + 50 
                
            max_text_height = available_height - (inner_padding * 2) - content_height 
            
            body_font, header_font, final_size, header_size, line_spacing, para_spacing, lines, text_height = self._get_dynamic_font(
                text, start_font_size=55, max_width=content_max_width, max_height=max_text_height
            )
            
            content_height += text_height
            total_box_height = content_height + (inner_padding * 2)
            
            # 5. تراز عمودی هوشمند کادر طلایی
            offset = max(0, (available_height - total_box_height) // 2)
            box_start_y = available_start_y + int(offset * 0.6)
            
            if box_start_y < available_start_y:
                box_start_y = available_start_y
                
            box_end_y = box_start_y + total_box_height
            
            # رسم کادر طلایی
            draw.rounded_rectangle(
                [(margin_x, box_start_y), (self.story_size[0] - margin_x, box_end_y)],
                radius=40,
                outline=self.color_gold,
                width=6
            )
            
            current_y = box_start_y + inner_padding
            
            if user_img_resized:
                img_x = (self.story_size[0] - img_w) // 2
                mask = Image.new("L", user_img_resized.size, 0)
                draw_mask = ImageDraw.Draw(mask)
                draw_mask.rounded_rectangle([(0, 0), user_img_resized.size], radius=20, fill=255)
                base_img.paste(user_img_resized, (img_x, int(current_y)), mask)
                current_y += img_h + 50
            
            for line in lines:
                if line.get('is_empty'):
                    current_y += final_size + line_spacing
                    continue
                    
                current_font = header_font if line['is_header'] else body_font
                current_size = header_size if line['is_header'] else final_size
                color = self.color_teal if line['is_header'] else self.color_text
                
                if HAS_RAQM:
                    line_width = current_font.getlength(line['text'], direction='rtl')
                    right_margin = (self.story_size[0] - content_max_width) / 2
                    x_pos = self.story_size[0] - right_margin - line_width
                    draw.text((x_pos, current_y), line['text'], font=current_font, fill=color, direction='rtl')
                else:
                    shaped_text = get_display(arabic_reshaper.reshape(line['text']))
                    line_width = current_font.getlength(shaped_text)
                    right_margin = (self.story_size[0] - content_max_width) / 2
                    x_pos = self.story_size[0] - right_margin - line_width
                    draw.text((x_pos, current_y), shaped_text, font=current_font, fill=color)
                
                current_y += current_size + line_spacing
                if line.get('is_paragraph_end'):
                    current_y += para_spacing

        # ذخیره خروجی نهایی
        final_img = base_img.convert("RGB")
        filename = f"story_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join(self.output_dir, filename)
        final_img.save(filepath, quality=95)
        
        return filename

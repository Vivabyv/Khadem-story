import os
from flask import Flask, render_template, request, url_for
from processor import StoryProcessor

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# مسیرهای دقیق برای هر دو قالب
TEMPLATE_TEXT_PATH = os.path.join('static', 'templates', 'template_text.jpg')
TEMPLATE_IMAGE_PATH = os.path.join('static', 'templates', 'template_image.jpg')
FONT_PATH = os.path.join('static', 'fonts', 'font.ttf')

# فراخوانی کلاس صحیح با هر سه ورودی
processor = StoryProcessor(TEMPLATE_TEXT_PATH, TEMPLATE_IMAGE_PATH, FONT_PATH)

@app.route('/', methods=['GET', 'POST'])
def index():
    output_image = None
    error_message = None
    
    if request.method == 'POST':
        mode = request.form.get('mode')
        text = request.form.get('text')
        image_file = request.files.get('image')
        
        if not text or text.strip() == '':
            error_message = "وارد کردن متن الزامی است."
        else:
            try:
                if mode == 'text_only':
                    filename = processor.generate_story('text_only', text)
                    output_image = url_for('static', filename=f'outputs/{filename}')
                    
                elif mode == 'text_and_image':
                    if not image_file or image_file.filename == '':
                        error_message = "در حالت 'متن + عکس'، آپلود تصویر الزامی است."
                    else:
                        filename = processor.generate_story('text_and_image', text, image_file.stream)
                        output_image = url_for('static', filename=f'outputs/{filename}')
                        
            except Exception as e:
                error_message = f"خطای پردازش: {str(e)}"
                
    return render_template('index.html', output_image=output_image, error=error_message)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
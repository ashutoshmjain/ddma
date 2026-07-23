import re

def main():
    with open('curator.html', 'r', encoding='utf-8') as f:
        html = f.read()
    
    # Find all content between <script> and </script>
    scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
    
    with open('scratch/curator_script.js', 'w', encoding='utf-8') as f:
        f.write('\n'.join(scripts))
    print("Successfully extracted JS to scratch/curator_script.js")

if __name__ == '__main__':
    main()

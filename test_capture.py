import mss
from PIL import Image

with mss.mss() as sct:
    shot = sct.grab({'left':39, 'top':282, 'width':256, 'height':149})
    img = Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')
    img.save('test_capture.png')
    print('test_capture.png に保存しました')
    print('open test_capture.png で確認してください')

$BLENDERPY -m ensurepip --default-pip
wget https://raw.githubusercontent.com/blendernc/blendernc/master/requirements.txt
wget https://github.com/blendernc/blendernc/archive/refs/heads/dev.zip -O blendernc.zip
$BLENDERPY -m pip install -r requirements.txt
blender --background --python ./bpy_activate_addon.py
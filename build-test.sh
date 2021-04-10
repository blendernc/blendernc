$BLENDERPY -m ensurepip --default-pip
wget https://raw.githubusercontent.com/blendernc/blendernc/master/requirements.txt
$BLENDERPY -m pip install -r requirements.txt
blender --background --python ./bpy_activate_addon.py
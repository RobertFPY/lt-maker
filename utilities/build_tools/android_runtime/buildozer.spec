[app]

title = LT Android Runtime
package.name = ltandroidruntime
package.domain = org.lextalionis
android.entrypoint = org.lextalionis.android.LtPythonActivity
source.dir = ./staging
source.include_exts = py,json,png,ogg,idx,orderkeys,ico,txt
version = 0.4.0
requirements = hostpython3==3.11.9,python3==3.11.9,pygame-ce==2.3.2,android
orientation = landscape
fullscreen = 1
icon.filename = %(source.dir)s/android_icon.png
presplash.filename = %(source.dir)s/android_presplash.png

android.api = 36
android.minapi = 26
android.ndk = 29
android.numeric_version = 1026400
android.archs = arm64-v8a
android.accept_sdk_license = True
android.private_storage = True
android.release_artifact = apk
android.logcat_filters = *:S python:D SDL:D AndroidRuntime:E
android.add_src = ./android_native/java
p4a.hook = ./android_native/p4a_hook.py

p4a.bootstrap = sdl2
p4a.local_recipes = ./p4a-recipes
p4a.url = https://github.com/kivy/python-for-android.git
p4a.branch = v2026.05.09
p4a.commit = 58d21141f17c889bf8585f5665921d72028f8831

[buildozer]

log_level = 2
warn_on_root = 1

[app]

title = LT Android Probe
package.name = ltandroidprobe
package.domain = org.lextalionis
source.dir = ./staging
source.include_exts = py,png,ogg,json,txt
version = 0.1.0
requirements = hostpython3==3.11.9,python3==3.11.9,pygame-ce==2.3.2,android
orientation = landscape
fullscreen = 1
icon.filename = %(source.dir)s/probe.png
presplash.filename = %(source.dir)s/probe.png

android.api = 36
android.minapi = 26
android.ndk = 29
android.archs = arm64-v8a
android.accept_sdk_license = True
android.private_storage = True
android.logcat_filters = *:S python:D SDL:D AndroidRuntime:E

p4a.bootstrap = sdl2
p4a.local_recipes = ./p4a-recipes
p4a.url = https://github.com/kivy/python-for-android.git
p4a.branch = v2026.05.09

[buildozer]

log_level = 2
warn_on_root = 1

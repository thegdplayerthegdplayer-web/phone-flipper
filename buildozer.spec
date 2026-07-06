[app]
title = Phone Flipper
package.name = phoneflipper
package.domain = org.titan
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3,kivy==2.3.0,plyer,pillow
orientation = portrait
fullscreen = 0

# Samsung Galaxy A57 5G Modern Permissions
android.permissions = CAMERA,VIBRATE,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,ACCESS_WIFI_STATE,BLUETOOTH
android.api = 33
android.minapi = 24
android.accept_sdk_license = True

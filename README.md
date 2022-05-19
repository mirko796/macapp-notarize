# macapp-notarize
Python wrapper for simplifying the app notarization process on Mac OS \
Requires Python 3.x

## Installing
```
python3 notarize.py --install
```

Installs script to `/usr/local/bin/notarize`

## Uninstalling
```
python3 notarize.py --uninstall
```

Removes script from `/usr/local/bin/notarize`

## Usage
```
$ notarize --help
usage: notarize.py [-h] [-l {error,warning,info,debug}] -u USERNAME -p
                   PASSWORD -b BUNDLE_ID [-v] [--install] [--uninstall]
                   appfile

positional arguments:
  appfile

optional arguments:
  -h, --help            show this help message and exit
  -l {error,warning,info,debug}, --log-level {error,warning,info,debug}
                        log level (default: error)
  -u USERNAME, --username USERNAME
                        Username (appleid) (default: None)
  -p PASSWORD, --password PASSWORD
                        App-specific password. For more details see
                        https://support.apple.com/en-us/HT204397 (default:
                        None)
  -b BUNDLE_ID, --bundle-id BUNDLE_ID
                        Primary bundle id (default: None)
  -v, --verify-only
  --install             Install script to /usr/bin/local (default: False)
  --uninstall           Uninstall script from /usr/bin/local (default: False)
```

If notarization or verification fails exit code will be non zero.

## Examples

### Notarize myapp

```
notarize myapp.pkg -p app_specific_password -u my@email.com -l info -b BUNDLE.ID.STH.STH.STH
```

### Verify myapp (without notarizing)
```
notarize myapp.pkg --verify-only
```
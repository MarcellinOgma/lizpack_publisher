# LizPack Publisher

A QGIS plugin to publish and manage your projects directly from your [LizPack](https://lizpack.com) instance.

## Features

- **Authentication** — Secure JWT-based login to the LizPack API
- **Multi-instance support** — Select from your available LizPack instances
- **File explorer** — Browse, create folders, rename, copy, move and delete remote files
- **Upload** — Send individual files or entire folders (batched in a single HTTP request)
- **Project download** — Fetch a `.qgs`/`.qgz` project along with its dependencies (shapefiles, rasters, GeoJSON, QML...)
- **Publishing** — Automatic rewriting of PostGIS connections to target the instance's internal database
- **PostGIS import** — Import QGIS vector layers into the instance's PostGIS database
- **Non-blocking operations** — All network operations run in dedicated QThreads

## Requirements

- QGIS >= 3.16
- A [LizPack](https://lizpack.com) account with at least one active instance

## Installation

1. Clone or download this repository into your QGIS plugins folder:
   - **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\lizpack_publisher`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/lizpack_publisher`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/lizpack_publisher`
2. Restart QGIS
3. Enable the plugin via **Plugins > Manage and Install Plugins**

## Usage

1. Click the **LizPack Publisher** icon in the Web toolbar (or menu **Web > LizPack**)
2. Log in with your LizPack credentials
3. Select an instance
4. Browse files, upload projects or import PostGIS layers

## Project structure

| File | Description |
|---|---|
| `__init__.py` | QGIS entry point (`classFactory`) |
| `plugin.py` | Main plugin class, menu and toolbar management |
| `dialog.py` | User interface (QDialog) |
| `sftp_client.py` | HTTP client for the LizPack API (auth, files, PostGIS) |
| `workers.py` | QThreads for async operations (upload, download, import...) |
| `metadata.txt` | QGIS plugin metadata |

## License

LizPack / GEODONNEE INC

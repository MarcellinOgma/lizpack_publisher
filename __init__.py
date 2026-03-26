def classFactory(iface):
    from .plugin import LizpackPublisherPlugin
    return LizpackPublisherPlugin(iface)

from octo_bots_python.filters.filter import Filter


class FiltersLoader:
    filter_classes = {}

    @staticmethod
    def load_filter(type_name: str, f: dict):
        if type_name not in FiltersLoader.filter_classes.keys():
            raise Exception("Unknown type name given for filters loader")
        return FiltersLoader.filter_classes[type_name].create_filter(f)

    @staticmethod
    def register_filter(clazz: type):
        if not issubclass(clazz, Filter):
            raise Exception("Invalid class given for filter loader")
        FiltersLoader.filter_classes[clazz.filter_type()] = clazz

from octo_bots_python.operations.operation import Operation


class OperationsLoader:
    operation_classes = {}

    @staticmethod
    def load_operation(type_name: str, f: dict):
        if type_name not in OperationsLoader.operation_classes.keys():
            raise Exception(f"Unknown type name given for operations loader [type: {type_name}]")
        return OperationsLoader.operation_classes[type_name].create_operation(f)

    @staticmethod
    def register_operation(clazz: type):
        if not issubclass(clazz, Operation):
            raise Exception("Invalid class given for operations loader")
        OperationsLoader.operation_classes[clazz.operation_type()] = clazz

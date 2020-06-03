import click
import os
from swagger_parser import SwaggerParser
import re

# Known extensions in lowercase
YAML_EXTENSIONS = [".yaml", ".yml"]
JSON_EXTENSIONS = [".json"]

# Choices provided when specifying the specification format
SPEC_JSON = "json"
SPEC_YAML = "yaml"
SPEC_CHOICES = [SPEC_JSON, SPEC_YAML]

Swagger_typeMap = {'number':'float', 'float': 'float', 'double': 'float', 'integer': 'int', 'int32': 'int', 'int64':'int', 'string':'string', 'boolean':'boolean', 'array':'array_ref'}

"""
The Generator is a bit wonky atm...
-> Not supported:
    min, max, ect len for fields.
    specs w/o definition, please do your defs!!
"""

class Generator():

    def __init__(self, specification_path):
        self.specification_path = specification_path
        self.parser = None
        self._load_spec()

        self.spec = self.parser.specification

        self.serializers = []

        self.api_definitions = None
        self.views = {}

        self.routes = []
        self.raw_routes = []

    @staticmethod
    def reindent_code(code):
        return '\n'.join(['\t'+e for e in code.split('\n')])

    def _load_spec(self):
        filename, file_ext = os.path.splitext(self.specification_path)
        if file_ext in YAML_EXTENSIONS:
            spec_format = SPEC_YAML
        elif file_ext in JSON_EXTENSIONS:
            spec_format = SPEC_JSON
        else:
            supported_extensions = ",".join(YAML_EXTENSIONS) + ',' + ','.join(JSON_EXTENSIONS)
            raise RuntimeError("Could not infer specification format from extension. Supported Extensions: {}".format(supported_extensions))

        click.secho("Using spec format '{}'".format(spec_format), fg="green")

        if spec_format == SPEC_YAML:
            with open(self.specification_path, "r") as f:
                self.parser = SwaggerParser(swagger_yaml=f)
        elif spec_format == SPEC_JSON:
            self.parser = SwaggerParser(swagger_path=self.specification_path)
        else:
            raise RuntimeError("Invalid spec_format {}".format(spec_format))

    def get_property_serializer_name(self, name, properties, parentName="Unknown"):
        type = properties.get('type')
        type = Swagger_typeMap.get(type)
        ref = properties.get('$ref')
        if ref is not None:
            type = 'ref'
            ref = '{}Serializer'.format(ref.split('/')[-1]) + '()'

        if type is None:
            raise RuntimeError("Property {} in definition {}, has no type or unknown.".format(name, parentName))

        serializerName = ""
        if type == 'float':
            serializerName = "serializers.FloatField()"
        if type == 'int':
            serializerName = "serializers.IntegerField()"
        if type == 'boolean':
            serializerName = "serializers.BooleanField()"
        if type == 'array_ref':
            # Build Array Serializer
            childName = self.get_property_serializer_name(name='child_{}'.format(name), properties=properties.get('items'))
            serializerName = "serializers.ListField(child={})".format(childName)
        if type == 'string':
            serializerName = "serializers.CharField()"
        if type == 'ref':
            serializerName = ref
        return serializerName

    def _generate_property_serializer(self, name, properties, parentName):
        # TODO -> Parse optional properties for the element.
        # TODO Support Layered parsing ( should just be doable w/ recursion.)

        serializerName = self.get_property_serializer_name(name, properties)
        code = '{0} = ' + serializerName
        code = code.format(name)
        return code

    def _generate_serializer(self, name, fields):
        code = "class {}Serializer(serializers.Serializer):\n".format(name)

        type = fields.get('type', None)
        if type is None:
            raise RuntimeError("Definition for {}, has no type.".format(name))
        if type != 'object':
            return []

        properties = fields.get('properties', None)
        if properties is None:
            raise RuntimeError("Definition for object {} has no properties.".format(name))

        for propertyName in properties:
            _code = self._generate_property_serializer(propertyName, properties.get(propertyName), name)
            _code = '\t{}\n'.format(_code)
            code += _code
        # print(code)

        return (name, code)

    def _extract_definitions(self):
        """
        Extracts all the definitions from a swagger-parser
        """

        definitions = self.spec.get('definitions', None)
        if definitions is None:
            return []
        def_keys = definitions.keys()

        serializers = []
        for key in def_keys:
            # generate a Serializer for that given key
            serializer = self._generate_serializer(key, definitions.get(key))
            serializers.append(serializer)
            self.serializers.append(serializer[1])

        return serializers

    def _generateIOParserCode(self, io):
        requiresAuth = False
        code = ""
        variable_names = []
        path_variables = []
        for key in io.keys():
            if key == 'body':
                # parse body argument
                body = io.get(key)
                if body is not None:
                    schema = body.get('schema')
                    ref = schema.get('$ref')
                    if ref is not None:
                        definitionRef = ref.split('/')[-1]
                        serializerName = '{}Serializer'.format(definitionRef)
                        code += 'body_serializer = {}(data=request.data)\n'.format(serializerName)
                        code += 'body = None\n'
                        code += 'if body_serializer.is_valid():\n'
                        code += '\tbody = body_serializer.data\n'
                    else:
                        type = schema.get('type')
                        ref = schema.get('items').get('$ref')
                        if type == 'array':
                            if ref is not None:
                                definitionRef = ref.split('/')[-1]
                                serializerName = '{}Serializer'.format(definitionRef)
                                code += 'body_serializer = serializers.ListField(child={}, data=request.data)\n'.format(
                                    serializerName)
                                code += 'body = None\n'
                                code += 'if body_serializer.is_valid():\n'
                                code += '\tbody = body_serializer.data\n'
                            else:
                                print('Please use a definition, not inline-types.')
                        else:
                            print(type)
                            print(body)
                variable_names.append(key)
            else:
                info = io.get(key)
                if info.get('in') == 'query':
                    code += "{0} = request.query_params.get('{0}')\n".format(key)
                    variable_names.append(key)
                elif info.get('in') == 'path':
                    path_variables.append(key)
                    variable_names.append(key)
                elif info.get('in') == 'formData':
                    # TODO -> verify that this actually parses formData
                    code += "{0} = request.data.get('{0}')\n".format(key)
                    variable_names.append(key)
                elif info.get('in') == 'header':
                    # TODO For now, just pass through the token ??
                    if 'key' in key or 'token' in key:
                        code += "token = request.META.get('{0}')\n".format(key)
                        code += "if not verifyToken(token):\n"
                        code += "\treturn Response(status=401)\n"
                else:
                    print(key)
                    print(info)
        return path_variables, variable_names, code, requiresAuth

    def _generate_APIView_FunctionStub(self, parentName, method, io):
        """
        returns a function that maps that method.
        + given i/o
        """
        path_variables, variables, _io_code, requiresAuth = self._generateIOParserCode(io.get('parameters'))

        path_variables = ['self, request'] + path_variables
        code = "def {}({}):\n".format(method, ', '.join(path_variables))
        _io_code = self.reindent_code(_io_code)
        code += (_io_code + '\n') if len(_io_code.strip()) > 0 else ""

        # Locate the handler and if found, pass all parsed vars to it.
        code += "\thandler = findHandler('{}_{}')\n".format(parentName, method)
        code += "\tif handler is not None:\n"

        # re-map the variables so they are passed to a named parameter
        variables = ['{0}={0}'.format(e) for e in variables]
        code += "\t\treturn handler({})\n".format(', '.join(variables))

        # Add a default Response with 204 (No-content)
        code += '\treturn Response(status=204)\n'
        return code, requiresAuth

    def _generate_APIView(self, path, verbs):
        """
        Output a tuple of endpoint url + code
        """
        requiresAuth = False
        parts = [e for e in path.split('/') if len(e) > 0]
        modelName = "_".join([e.replace('{', '').replace('}', '') for e in parts]) + "View"
        django_path = translate_SwaggerURL_toDjango(path, verbs)
        django_route = "path('{0}', {1}.as_view(), name={1}),".format(django_path, modelName)
        # django_route = "re_path(r'^{0}', {1}.as_view()),".format(django_path, modelName)
        # django_route = "path,".format(django_path, modelName)

        print("Generating APIView {} @ {}".format(modelName, django_path))

        code = "class {}(APIView):\n\t\n".format(modelName)
        # code += "\tqueryset = ''\n\n"

        _code = ""
        method_names = []
        for method, io in verbs.items():
            fn_code, ra = self._generate_APIView_FunctionStub(modelName, method, io)
            requiresAuth = requiresAuth or ra
            # re-indent the code:
            fn_code = self.reindent_code(fn_code) + '\n'
            _code += fn_code

        code += _code

        # save the ViewModel code
        self.views[modelName] = code

        # save the route
        self.routes.append(django_route)
        self.raw_routes.append((django_path, modelName))

    def _generateAPIViews(self):
        for path, verbs in self.parser.paths.items():
            self._generate_APIView(path, verbs)

    """ File generation """

    @staticmethod
    def loadTemplate(name):
        template = ""
        with open(name, 'r') as fp:
            template = fp.read()
        template = template.replace('    ','\t')
        return template

    @staticmethod
    def saveFile(name, data):
        with open(name, 'w') as fp:
            fp.write(data)

    def saveSerializers(self):
        """ TODO -> sort by dependence. """
        code = self.loadTemplate('templates/serializers.py') + '\n'
        for serializer_code in self.serializers:
            code += serializer_code + '\n'
        self.saveFile('output/serializers.py', code)

    def saveViews(self):
        """ TODO -> sort by dependence. """
        code = self.loadTemplate('templates/views.py') + '\n'
        for viewName in self.views:
            view_code = self.views.get(viewName)
            code += view_code + '\n'
        self.saveFile('output/views.py', code)

    def _sortURLs(self):
        # Idea! generate a tree from the URLs, w/ shunting yard, with low weights for parameters
        # TODO -> Implement
        pass

    def saveUrls(self):
        code = self.loadTemplate('templates/urls.py') + '\n'

        """
        router.register(r'heroes', views.HeroViewSet)

        # Wire up our API using automatic URL routing.
        # Additionally, we include login URLs for the browsable API.
        urlpatterns = [
            path('', include(router.urls)),
        ]
        
        for rp in self.raw_routes:
            code += "router.register(r'{0}', {1}, basename='{1}')\n".format(rp[0], rp[1])
        """
        """
        code += 'urlpatterns = [\n'
        for path in self.routes:
            code += '\t' + path + '\n'
        code += ']\n'
        """

        # Sort the routes:
        self.routes.sort(key=len, reverse=True)

        code += "urlpatterns = [\n"
        code += "\tpath('admin/', admin.site.urls),\n"
        for path in self.routes:
            code += '\t' + path + '\n'
        code += "]\n"
        self.saveFile('output/urls.py', code)

    def generate(self):
        # Resolve Definitions
        self.api_definitions = self._extract_definitions()

        # generate APIView code + routes
        self._generateAPIViews()

        # Use the serializers template to save definitions
        self.saveSerializers()

        # Use the Views Template to save api_views
        self.saveViews()

        # Use the Views Template to save api
        self.saveUrls()


def extract_Definitions(parser):
    """
    Extracts all the definitions from a swagger-parser
    """

    definitions = parser.specification.get('definitions', None)
    if definitions is None:
        return []
    def_keys = definitions.keys()

    serializers = []
    for key in def_keys:
        # generate a Serializer for that given key
        serializer = generate_Serializer(key, definitions.get(key))
        serializers.append(serializer)

    return serializers


def load_spec(specification_path, spec_format=None):
    # If the swagger spec format is not specified explicitly, we try to
    # derive it from the specification path
    if not spec_format:
        filename, file_ext = os.path.splitext(specification_path)
        if file_ext in YAML_EXTENSIONS:
            spec_format = SPEC_YAML
        elif file_ext in JSON_EXTENSIONS:
            spec_format = SPEC_JSON
        else:
            raise RuntimeError("Could not infer specification format from extension. Use "
                               "--spec-format to specify it explicitly.")
    click.secho("Using spec format '{}'".format(spec_format), fg="green")

    parser = None

    if spec_format == SPEC_YAML:
        with open(specification_path, "r") as f:
            parser = SwaggerParser(swagger_yaml=f)
    elif spec_format == SPEC_JSON:
        parser = SwaggerParser(swagger_path=specification_path)
    else:
        raise RuntimeError("Invalid spec_format {}".format(spec_format))

    # Build (path, http_verb) => operation mapping
    api_definitions = extract_Definitions(parser)

    # self._classes = {}
    return
    for path, verbs in parser.paths.items():
        generate_ViewModel(path, verbs)


def translate_SwaggerURL_toDjango(path, verbs):
    """
    URL Params currently are just passed as strings.
    -> TODO -> use the verbs url
    """

    def transform(part):
        matches = re.findall(r"(?:\{)(.+)(?:\})", part)
        if len(matches) > 0:
            return "<str:{}>".format(matches[0])
        return part

    parts = [transform(e) for e in path.split('/') if len(e) > 0]

    djangoURL = "/".join(parts)

    return djangoURL







@click.command()
@click.argument("specification_path", type=click.Path(dir_okay=False, exists=True))
def main(specification_path):
    gen = Generator(specification_path)
    gen.generate()


if __name__ == '__main__':
    main()

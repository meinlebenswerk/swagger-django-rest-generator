# Django-REST-Swagger generator
This is a simple, not yet fully functional, Script that takes in a swagger(.json/.yaml...) file and generates the necessary routes and paths for django-rest.

This Project was heavily influenced by [swagger-django-generator](https://github.com/praekelt/swagger-django-generator) by [Praekelt Consulting
](https://github.com/praekelt). But That project only generates django or aiohttp code and it does that a lot better than this hacked together mess :)

Important Disclaimer:<br>
This is an hacked-together mess, that barely works...<br>
If I happen to find some time, I will attempt to fix this, but for my current use-case all I could spare was a few days...<br>
So Please excuse the mess :)

## Running
 - Clone the Project with git
 - install some dependencies with pip (click and swagger_parser should suffice)
 - run the rest_generator via `python rest_generator.py <inputfile>`

The generator automatically detects the JSON/YAML format and parses that,
the output will be written to `./output`.

## Output-format:
- serializers.py -> all the serializers required to parse the input
- urls.py -> the routing for your api
- views.py -> the generated APIView stubs

#### Endpoint Naming and handling

-> Since I wanted to be able to change my API-Description and not have to rewrite the whole application-code again, the views.py only contains some boilerplate code.

All the Implementation specific details will be searched in api_implemetation.py, and if nothing was found, the Server responds, with a 204 (No-content).

This search works as follows:<br>
A POST request to `/v2/pet/petId/uploadImageView` would be routed to the `v2_pet_petId_uploadImageView` APIView, which in turn searches for the function `v2_pet_petId_uploadImageView_post` in the implementation file.

##### Parameters
Parameters in the request-body will be parsed via the appropriate serializer. <br>
URL-Parameters will be passed as a string, by name into the handler.<br>
The same goes for Query-String Parameters.


## Issues
- Parsing & passing tokens works via a stub in the views.py<br>
It should be handled by the Django-REST Framework, as it already contains code for that.

- URLs, there are a lot of quirks here... (e.g. ambiguous URLs (like /user/<username> + /user/logout -> I need to sort these better :/) )

- Probably a lot more I don't remember.#   s w a g g e r - d j a n g o - r e s t - g e n e r a t o r  
 
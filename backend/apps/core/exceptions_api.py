from rest_framework import status
from rest_framework.exceptions import APIException


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The request conflicts with the current state of the resource."
    default_code = "conflict"


class Gone(APIException):
    status_code = status.HTTP_410_GONE
    default_detail = "This resource is no longer available."
    default_code = "gone"

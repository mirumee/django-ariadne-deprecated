import json

from ariadne.constants import (
    DATA_TYPE_JSON, HTTP_STATUS_200_OK, HTTP_STATUS_400_BAD_REQUEST
)
from ariadne.exceptions import GraphQLError, HttpError
from django.http import HttpRequest, HttpBadRequestError, JsonResponse
from django.views import TemplateView
from graphql import format_error, graphql
from graphql.execution import ExecutionResult


class GraphQLView(TemplateView):
    template_name = "ariadne/playground.html"

    def post(self, request):
        try:
            return self.handle_post(request)
        except GraphQLError as error:
            return self.handle_graphql_error(error)
        except HttpError as error:
            return self.handle_http_error(error)

    def handle_post(self, request):
        data = self.get_request_data(request)
        result = self.execute_query(environ, data)
        return self.return_response_from_result(result)

    def handle_graphql_error(
        self, error: GraphQLError, start_response: Callable
    ) -> List[bytes]:
        start_response(
            HTTP_STATUS_400_BAD_REQUEST, [("Content-Type", CONTENT_TYPE_JSON)]
        )
        error_json = {"errors": [format_error(error)]}
        return [json.dumps(error_json).encode("utf-8")]

    def handle_http_error(
        self, error: HttpError, start_response: Callable
    ) -> List[bytes]:
        start_response(error.status, [("Content-Type", CONTENT_TYPE_TEXT_PLAIN)])
        response_body = error.message or error.status
        return [str(response_body).encode("utf-8")]

    def get_request_data(self, request: HttpRequest) -> dict:
        if request.content_type != DATA_TYPE_JSON:
            raise HttpBadRequestError(
                "Posted content must be of type {}".format(DATA_TYPE_JSON)
            )

        request_body = self.get_request_body(request)
        data = self.parse_request_body(request_body)
        if not isinstance(data, dict):
            raise GraphQLError("Valid request body should be a JSON object")

        return data

    def get_request_body(self, request: HttpRequest) -> bytes:
        request_body = request.read()
        if not request_body:
            raise HttpBadRequestError("Request body cannot be empty")
        return request_body

    def parse_request_body(self, request_body: bytes) -> Any:
        try:
            return json.loads(request_body)
        except ValueError:
            raise HttpBadRequestError("Request body is not a valid JSON")

    def execute_query(self, request: HttpRequest, data: dict) -> ExecutionResult:
        return graphql(
            self.schema,
            data.get("query"),
            root=self.get_query_root(request, data),
            context=self.get_query_context(request, data),
            variables=self.get_query_variables(data.get("variables")),
            operation_name=data.get("operationName"),
        )

    def get_query_root(
        self, request: HttpRequest, data: dict  # pylint: disable=unused-argument
    ) -> Any:
        """Override this method in inheriting class to create query root."""
        return None

    def get_query_context(self, request: HttpRequest, data: dict) -> Any:
        """Override this method in inheriting class to create query context."""
        return {"request": request, "data": data}

    def get_query_variables(self, variables):
        if variables is None or isinstance(variables, dict):
            return variables
        raise GraphQLError("Query variables must be a null or an object")

    def return_response_from_result(self, result: ExecutionResult) -> JsonResponse:
        status = HTTP_STATUS_200_OK
        response = {}
        if result.errors:
            response["errors"] = [format_error(e) for e in result.errors]
        if result.invalid:
            status = HTTP_STATUS_400_BAD_REQUEST
        else:
            response["data"] = result.data
        return JsonResponse(response, status=status)
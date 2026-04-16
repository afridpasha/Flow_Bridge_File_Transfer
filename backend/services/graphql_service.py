"""
GraphQL Service — Query interface for FlowBridge data.
"""
try:
    from graphql import build_schema, graphql_sync
    GRAPHQL_AVAILABLE = True
except ImportError:
    GRAPHQL_AVAILABLE = False


SCHEMA_SDL = """
type File {
    id: String!
    filename: String!
    size: Int!
    content_type: String!
    created_at: String!
    owner: String!
}

type User {
    id: String!
    username: String!
    email: String!
    file_count: Int!
}

type Query {
    files(owner: String, limit: Int): [File]
    file(id: String!): File
    users(limit: Int): [User]
    user(id: String!): User
}
"""


class GraphQLSchema:
    def __init__(self):
        self.available = GRAPHQL_AVAILABLE
        if GRAPHQL_AVAILABLE:
            self.schema = build_schema(SCHEMA_SDL)

    def is_available(self):
        return self.available


class GraphQLExecutor:
    def __init__(self):
        self.schema_obj = GraphQLSchema()
        self._resolvers = {}

    def execute(self, query, variables=None, context=None):
        if not self.schema_obj.available:
            return {"errors": [{"message": "graphql-core not installed"}]}

        # Simple mock resolver for demonstration
        result = graphql_sync(
            self.schema_obj.schema,
            query,
            variable_values=variables or {},
            context_value=context or {},
        )
        return {
            "data": result.data,
            "errors": [str(e) for e in result.errors] if result.errors else None,
        }

    def get_schema_sdl(self):
        return SCHEMA_SDL

    def stats(self):
        return {
            "available": self.schema_obj.available,
            "schema_types": 3,
        }


_executor = GraphQLExecutor()


def get_graphql_executor():
    return _executor

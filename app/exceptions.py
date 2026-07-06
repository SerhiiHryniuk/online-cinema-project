class BaseAppError(Exception):
    pass


class BaseEmailError(BaseAppError):
    pass


class TokenError(Exception):
    pass


class InvalidTokenTypeError(TokenError):
    pass


class MinioConnectionError(BaseAppError):
    pass


class MinioFileUploadError(BaseAppError):
    pass


class CartError(Exception):
    pass


class CartNotFound(CartError):
    def __init__(self, message="Cart not found"):
        super().__init__(message)


class MovieError(Exception):
    pass


class MovieNotFound(MovieError):
    def __init__(self, message="Movie not found"):
        super().__init__(message)

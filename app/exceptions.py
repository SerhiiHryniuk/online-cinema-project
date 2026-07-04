class BaseAppError(Exception):
    pass


class BaseEmailError(BaseAppError):
    pass


class TokenError(Exception):
    pass


class InvalidTokenTypeError(TokenError):
    pass

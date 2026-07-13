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
    def __init__(self, message: str = "Cart not found") -> None:
        super().__init__(message)


class MovieError(Exception):
    pass


class MovieNotFound(MovieError):
    def __init__(self, message: str = "Movie not found") -> None:
        super().__init__(message)


class OrderError(Exception):
    pass


class EmptyCartError(OrderError):
    def __init__(self, message: str = "Cart is empty.") -> None:
        super().__init__(message)


class NoAvailableMoviesError(OrderError):
    def __init__(self, message: str = "No available movies in cart.") -> None:
        super().__init__(message)


class AllMoviesPurchasedError(OrderError):
    def __init__(self, message: str = "All movies in cart are already purchased.") -> None:
        super().__init__(message)


class DuplicatePendingOrderError(OrderError):
    def __init__(self, message: str = "A pending order with the same movies already exists.") -> None:
        super().__init__(message)

class SecurityError(Exception):
    """Raised when security validation fails"""
    pass


class DocumentFetchError(Exception):
    """Raised when document fetching fails"""
    pass


class DocumentParseError(Exception):
    """Raised when document parsing fails"""
    pass


class UnsupportedFormatError(Exception):
    """Raised when document format is not supported"""
    pass
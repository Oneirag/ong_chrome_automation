class CopilotError(Exception):
    """Base exception for Copilot-related errors."""
    pass


class CopilotExceedsMaxLengthError(CopilotError):
    """Exception raised when the input exceeds the maximum length allowed by Copilot."""
    def __init__(self, message="Input exceeds the maximum length allowed by Copilot.", current_length=0, max_length=0):
        self.current_length = current_length
        self.max_length = max_length
        super().__init__(message)

    def __str__(self):
        return f"{super().__str__()} (Current length: {self.current_length}, Max length: {self.max_length})"


class CopilotTimeoutError(CopilotError, TimeoutError):
    """Exception raised when a Copilot operation times out."""
    pass

if __name__ == '__main__':
    raise CopilotTimeoutError("Operation timed out while waiting for Copilot response.")

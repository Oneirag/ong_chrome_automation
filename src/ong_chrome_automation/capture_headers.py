from playwright.sync_api import Browser, BrowserContext


class CaptureHeaders:
    def capture_headers_request_response(self, request_or_response):
        if not self.capture_headers:
            return
        headers = request_or_response.headers
        for header, value in headers.items():
            if value:
                if isinstance(self.capture_headers, list):
                    if header not in self.capture_headers:
                        continue
                if self.print_headers:
                    print(header, value)
                self.__headers[header] = value
        
    
    def __init__(self, context: BrowserContext, capture_headers: bool | list, print_headers: bool=False):
        self.print_headers = print_headers
        self.__headers = dict()
        self.capture_headers = capture_headers
        if capture_headers:
            context.on("request", self.capture_headers_request_response)
            # Intesting headers appear just on requests
            # context.on("response", self.capture_headers_request_response)

        
    @property
    def headers(self) -> dict:
        return self.__headers

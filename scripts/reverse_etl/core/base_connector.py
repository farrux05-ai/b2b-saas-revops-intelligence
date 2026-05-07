import time
import abc
import logging

class BaseConnector(abc.ABC):
    """
    Abstract Base Class for all Reverse ETL destinations.
    Provides standard retry logic and rate limit handling.
    """
    def __init__(self, name, is_simulation=False):
        self.name = name
        self.is_simulation = is_simulation
        self.logger = logging.getLogger(f"RETL.{name}")
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def execute_with_retry(self, func, max_retries=3, backoff_factor=2, *args, **kwargs):
        """Executes a function with exponential backoff on failure."""
        retries = 0
        while retries < max_retries:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # In real life, catch specific exceptions like requests.exceptions.RequestException
                retries += 1
                wait_time = backoff_factor ** retries
                self.logger.warning(f"Error occurred: {str(e)}. Retrying in {wait_time}s ({retries}/{max_retries})")
                time.sleep(wait_time)
        self.logger.error(f"Max retries reached. Failed to execute.")
        raise Exception(f"Max retries reached for {self.name} connector.")

    @abc.abstractmethod
    def sync(self, df):
        """Main sync method to be implemented by child classes."""
        pass

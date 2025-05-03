import io
import pandas as pd
import logging

from service import dbagent as engine


logger = logging.getLogger(__name__)


class Report:
    SETTINGS = {}
    def __init__(self, process_args, engine):
        self.engine = engine
        self.input_args = process_args
        self.placeholders = {}
        
    def fetch(self):
        logger.debug(self.input_args)
        self.placeholders = self.get_trade_detail()
        logger.debug(str(self.placeholders))
        return {**self.placeholders, **self.SETTINGS}

    def get_trade_detail(self):
        query = """
        SELECT * FROM [crm].[xxxxxxx]
        WHERE (tradeId = ?)
        """
        df = self.engine.read_sql(query, none_on_empty_df=True, params=(self.input_args.get('tradeid'), ))
        return df.to_dict('records')[0]
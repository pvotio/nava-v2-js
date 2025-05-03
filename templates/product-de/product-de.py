import threading
import itertools
import matplotlib.pyplot as plt
import io
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.dates as mdates
from datetime import datetime, timedelta



font = {
    "family": "sans-serif",
    "sans-serif": "DejaVu Sans",
    "weight": "light",
    "size": 6,
}

mpl.rc("font", **font)


def get_header():
    image = "{{path:uploads/logo.svg}}"
    name = "Produktreport"
    date = datetime.now().strftime("%d.%m.%Y")
    html = f"""
<div style="display: flex; justify-content: space-between; width:85.8%; font-size:10px; padding-left:7.2%; padding-top: 20px;">
            <img src="{image}" alt="Logo" style="width:90px;">
            <span style="font-size:7px; color: lightgrey;">{name}, {date}</span>
        </div>
    """
    return html
    

def get_footer():
    html = """
    <div style="display: flex; justify-content: space-between; align-items: center; width: 93%; font-size: 7px; color: lightgrey; padding-bottom: 20px;">
    <div style="flex-grow: 0; flex-shrink: 0; text-align: left; padding-left: 60px;">
        <span>Picard Angst AG, Bahnhofstr. 13-15, CH-8808 Pfäffikon SZ</span>
    </div>
    <div style="flex-grow: 1; text-align: right;">
        <span><span class="pageNumber"></span>/<span class="totalPages"></span></span>
    </div>
</div>
    """
    return html

class Report:

    SETTINGS = {
        "header": get_header(),
        "footer": get_footer(),
    }
    
    def __init__(self, process_args, engine):
        self.engine = engine
        self.input_args = process_args
        self.placeholders = {}
    

    def fetch(self):
        threads = []

        for func in [
            self.get_product_detail,
            self.get_table1,
            self.get_table2,
            self.get_table2b,
            self.get_table3,
            self.get_table4,
            self.get_table4b,
            self.get_table5,
            self.get_table6,
            self.get_chart1,
            self.get_chart2,
        ]:
            t = threading.Thread(target=func)
            threads.append(t)

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        return {**self.placeholders, **self.SETTINGS}

    def fetch_data(self):
        placeholders = {
            **self.product_detail,
            "table1": self.get_table1(),
            "table2": self.get_table2(),
            "table2b": self.get_table2b(),
            "table3": self.get_table3(),
            "table4": self.get_table4(),
            "table4b": self.get_table4b(),
            "table5": self.get_table5(),
            "table6": self.get_table6(),
            "product_chart": self.get_chart1(),
            "basiswert_chart": self.get_chart2(),
        }
        return placeholders

    def get_product_detail(self):
        query = """
        SELECT TOP 1 [titleDe] AS [titleDe],
                [nameDe] AS [nameDe],
                [issuerName] AS [issuerName],
                isin AS isin,
                valor AS valor,
                paNr AS paNr,
                [productTypeDe] AS [productTypeDe],
                wkn AS wkn,
                [svspGroupDe] AS [svspGroupDe],
                product_url AS product_url,
                [CurrencyDE] AS [CurrencyDE],
                [nominalDE] AS [nominalDE],
                [isQuantoDE] AS [isQuantoDE],
                [issuePriceDE] AS [issuePriceDE],
                [issuerName] AS [issuerName],
                [guarantorName] AS [guarantorName],
                [capDE] AS [capDE],
                [bonusLevelDE] AS [bonusLevelDE],
                [participationMinDE] AS [participationMinDE],
                [participationMaxDE] AS [participationMaxDE],
                [capitalProtectionDE] AS [capitalProtectionDE],
                [settlementTypeDe] AS [settlementTypeDe],
                [observationTypesDE] AS [observationTypesDE],
                [lawDE] AS [lawDE],
                [jurisdictionDE] AS [jurisdictionDE],
                [initialFixingDateDE] AS [initialFixingDateDE],
                [paymentDateDE] AS [paymentDateDE],
                [redemptionDateDE] AS [redemptionDateDE],
                [redeemedondateDE] AS [redeemedondateDE],
                [finalFixingDateDE] AS [finalFixingDateDE],
                [CouponobservationTypesDE] AS [CouponobservationTypesDE],
                [couponTextDE] AS [couponTextDE],
                [CouponPaymentsNumber] as [CouponPaymentsNumber],
                [autocalltextDE] as [autocalltextDE],
                [autocallCountDE] as [autocallCountDE],
                [autocalldatenextDE] as [autocalldatenextDE],
                [dropback_distributionDE] as [dropback_distributionDE],
                [minCouponDE] AS [minCouponDE],
                [isMemoryCouponDE] AS [isMemoryCouponDE],
                [maxCouponDE] AS [maxCouponDE],
                [latestPriceDateDE] AS [latestPriceDateDE],
                [latestAskDE] AS [latestAskDE],
                [latestBidDE] AS [latestBidDE],
                [redemptionpriceDE] AS [redemptionpriceDE],
                [product_date] AS [product_date]
        FROM clients.products_header_info
        WHERE (isin = ?) AND (product_date = ?)
        """
        df = self.engine.read_sql(query, none_on_empty_df=True,  params=((self.input_args.get("isin"), self.input_args.get("date"))))
        current_date = datetime.now().strftime("%Y/%m/%d")  # Get current date in "dd.mm.yyyy" format
        df["product_date"] = np.where(df["product_date"] == "latest", current_date, df["product_date"])
        df["product_date"] = pd.to_datetime(df["product_date"])
        df["product_date"] = df["product_date"].dt.strftime("%d.%m.%Y")
        if not len(df):
            return {}

        self.placeholders = {**self.placeholders, **df.to_dict("records")[0]}
        return 

    def get_table1(self):
        query = """SELECT TOP 100 [Underlying_BBG] AS [BBG],
           [Underlying_NameDE] AS [Basiswert],
           [CurrencyDE] AS [Währung],
           [Initial_FixingDE] AS [Anfangsfixierung],
           [Strike_Level_PctDE] AS [Strike Level in %],
           [Strike_PriceDE] AS [Strike],
           [Cap_Level_PctDE] AS [Cap Level in %],
           [Cap_PriceDE] AS [Cap],
           [Underlying_Last_PriceDE] AS [Kurs],
           [Underlying_Last_Price_Date_UTCDE] AS [Kursdatum],
           [Pct_InitialFixingDE] AS [% zur Anfangsfixierung]
FROM clients.products_underlyings
WHERE (isin = ?) AND (product_date = ?)
GROUP BY [Underlying_BBG],
         [Underlying_NameDE],
         [CurrencyDE],
         [Initial_FixingDE],
         [Strike_Level_PctDE],
         [Strike_PriceDE],
         [Cap_Level_PctDE],
         [Cap_PriceDE],
         [Underlying_Last_PriceDE],
         [Underlying_Last_Price_Date_UTCDE],
         [Pct_InitialFixingDE];"""
         
        df = self.engine.read_sql(query, none_on_empty_df=True, params=((self.input_args.get("isin"), self.input_args.get("date"))))
        ##df["Kursdatum"] = pd.to_datetime(df["Kursdatum"]).dt.date
        df = df.dropna(axis=1, how='all')
        df = self.apply_german_d3_formatting(df, 2)
        self.placeholders["table1"] = self.to_mdl_html(df)
        return


    def get_table2(self):
        query = """SELECT TOP 100
           [observationTypeDE] AS [Beobachtungstyp],
           [monitoringTypeDE] AS [Beobachtungsart],
           [observationdateDE] AS [Beobachtungstag],
           [paymentDateDE] AS [Zahlungstag],
           [observationlevelpct] AS [Beob. Level (%)]
FROM clients.products_upcoming_obs
WHERE (isin = ?) AND (product_date = ?)
GROUP BY [observationTypeDE],
         [monitoringTypeDE],
         [observationdateDE],
         [paymentDateDE],
         [observationlevelpct];"""

        df = self.engine.read_sql(query, none_on_empty_df=True, params=((self.input_args.get("isin"), self.input_args.get("date"))))
        # Filter columns where all values are the same and non-NaN
        df = df.dropna(axis=1, how='all')
        df = self.apply_german_d3_formatting(df, 2)
        self.placeholders["table2"] = self.to_mdl_html(df)
        return
    
    
    
    
    def get_table2b(self):
        query = """SELECT TOP 100
            [PaymentDate],
           [observationTypeDE] AS [Kupontyp],
           [observationDateDE] AS [Beobachtung],
           [PaymentDateDE] AS [Zahlung],
           [couponAmountPctDE] AS [in %]
            FROM clients.products_coupon_obs_paid
            WHERE (isin = ?) AND (product_date = ?)
            GROUP BY 
             [PaymentDate],
             [observationTypeDE],
             [observationDateDE],
             [paymentDateDE],
             [couponAmountPctDE]
            ORDER BY 
            [PaymentDate] DESC;""" 
             
        df = self.engine.read_sql(query, none_on_empty_df=True, params=((self.input_args.get("isin"), self.input_args.get("date"))))
         # Filter columns where all values are the same and non-NaN
        df = df.drop('PaymentDate', axis=1)
        df = df.dropna(axis=1, how='all')
        df = self.apply_german_d3_formatting(df, 3)
        def transform_dataframe(df):
            n_rows = len(df)
            if n_rows > 3:
                third = n_rows // 3
                # Calculate the number of rows for each section
                first_end = third
                second_end = 2 * third
                # Slice the DataFrame into three sections
                first_section = df.iloc[:first_end+1]
                second_section = df.iloc[first_end+1:second_end++2]
                third_section = df.iloc[second_end+2:]
                # Reset index for all sections
                first_section.reset_index(drop=True, inplace=True)
                second_section.reset_index(drop=True, inplace=True)
                third_section.reset_index(drop=True, inplace=True)
                # Concatenate the three sections side by side
                result = pd.concat([first_section, second_section, third_section], axis=1)
            else:
                # Handle cases when there are 7 rows or less
                result = df  # Placeholder for additional logic if needed
            return result
        transformed_df = transform_dataframe(df)
        transformed_df = transformed_df.dropna(axis=1, how='all')
        transformed_df.fillna('', inplace=True)
        self.placeholders["table2b"] = self.to_mdl_html(transformed_df)
        return
    
    

    def get_table3(self):
        query = """
SELECT TOP 20 [UnderlyingTicker] AS [BBG],
           [observationTypeDe] AS [Kupontyp],
           [monitoringTypeDe] AS [Beobachtungsart],
           [observationDateDE] AS [Beobachtungstag],
           [PaymentDateDE] AS [Zahlungstag],
           [couponAmountPctDE] AS [Kupon],
           [observationLevelPctDE] AS [Kupon Level %],
           [Coupon_Barrier_PriceDE] AS [Kupon Level],
           [minCouponAmountPctDE] AS [Min Kupon],
           [maxCouponAmountPctDE] AS [Max Kupon],
           [currencyDE] AS [Währung],
           [price_closeDE] AS [Kurs],
           [Pct_Coupon_BarrierDE] AS [% zum Kupon Level]
FROM clients.products_coupon_obs
WHERE (isin = ?) AND (product_date = ?)
GROUP BY [UnderlyingTicker],
         [Underlying_NameDE],
         [observationTypeDe],
         [monitoringTypeDe],
         [observationDateDE],
         [PaymentDateDE],
         [couponAmountPctDE],
         [observationLevelPctDE],
         [Coupon_Barrier_PriceDE],
         [minCouponAmountPctDE],
         [maxCouponAmountPctDE],
         [currencyDE],
         [price_closeDE],
         [price_dateDE],
         [Pct_Coupon_BarrierDE];
        """

        df = self.engine.read_sql(query, none_on_empty_df=True, params=((self.input_args.get("isin"), self.input_args.get("date"))))
         # Filter columns where all values are the same and non-NaN
        df = df.dropna(axis=1, how='all')
        df = self.apply_german_d3_formatting(df, 2)
        self.placeholders["table3"] = self.to_mdl_html(df)
        return

    def get_table4(self):
        query = """
SELECT TOP 1000 [UnderlyingTicker] AS [BBG],
           [observationTypeDe] AS [Beobachtungstyp],
           [observationDateDE] AS [Beobachtungstag],
           [PaymentDateDE] AS [Zahlungstag],
           [currencyDE] AS [Währung],
           [observationLevelPctDE] AS [Autocall Level %],
           [autocall_level_priceDE] AS [Autocall Level],
           [price_closeDE] AS [Kurs],
           [pct_autocall_levelDE] AS [% zum Autocall Level]
FROM clients.products_autocall_obs
WHERE (isin = ?) AND (product_date = ?)
GROUP BY [UnderlyingTicker],
         [Underlying_NameDE],
         [observationTypeDe],
         [observationDateDE],
         [PaymentDateDE],
         [currencyDE],
         [observationLevelPctDE],
         [autocall_level_priceDE],
         [price_closeDE],
         [price_dateDE],
         [pct_autocall_levelDE];
        """

        df = self.engine.read_sql(query, none_on_empty_df=True, params=((self.input_args.get("isin"), self.input_args.get("date"))))
         # Filter columns where all values are the same and non-NaN
        df = df.dropna(axis=1, how='all')
        df = self.apply_german_d3_formatting(df, 2)
        self.placeholders["table4"] = self.to_mdl_html(df)
        return



    
    def get_table4b(self):
        query = """SELECT TOP 100
            [PaymentDate],
           [observationTypeDE] AS [Beobachtungstyp],
           [observationDateDE] AS [Beobachtungstag],
           [PaymentDateDE] AS [Zahlungstag]
            FROM clients.products_issuercall_obs
            WHERE (isin = ?) AND (product_date = ?)
            GROUP BY 
             [PaymentDate],
             [observationTypeDE],
             [observationDateDE],
             [paymentDateDE]
            ORDER BY 
            [PaymentDate] DESC;""" 
             
        df = self.engine.read_sql(query, none_on_empty_df=True, params=((self.input_args.get("isin"), self.input_args.get("date"))))
         # Filter columns where all values are the same and non-NaN
        df = df.drop('PaymentDate', axis=1)
        df = df.dropna(axis=1, how='all')
        df = self.apply_german_d3_formatting(df, 3)
        def transform_dataframe(df):
            n_rows = len(df)
            if n_rows > 3:
                third = n_rows // 3
                # Calculate the number of rows for each section
                first_end = third
                second_end = 2 * third
                # Slice the DataFrame into three sections
                first_section = df.iloc[:first_end+1]
                second_section = df.iloc[first_end+1:second_end++2]
                third_section = df.iloc[second_end+2:]
                # Reset index for all sections
                first_section.reset_index(drop=True, inplace=True)
                second_section.reset_index(drop=True, inplace=True)
                third_section.reset_index(drop=True, inplace=True)
                # Concatenate the three sections side by side
                result = pd.concat([first_section, second_section, third_section], axis=1)
            else:
                # Handle cases when there are 7 rows or less
                result = df  # Placeholder for additional logic if needed
            return result
        transformed_df = transform_dataframe(df)
        transformed_df = transformed_df.dropna(axis=1, how='all')
        transformed_df.fillna('', inplace=True)
        self.placeholders["table4b"] = self.to_mdl_html(transformed_df)
        return
    








    def get_table5(self):
        query = """
SELECT TOP 50 [UnderlyingTicker] AS [BBG],
           [observationTypeDE] AS [Beobachtungstyp],
           [monitoringTypeDE] AS [Beobachtungsart],
           [First_Barrier_hit_DateDE] AS [Barriere Kontakt],
           [currencyDE] AS [Währung],
           [observationLevelPctDE] AS [Barriere in %],
           [BarrierDE] AS [Barriere],
           [price_closeDE] AS [Kurs],
           [Distance_dailyDE] AS [% zur Barriere]
FROM clients.products_barrier_obs
WHERE (isin = ?) AND (product_date = ?)
GROUP BY [UnderlyingTicker],
         [Underlying_NameDE],
         [observationTypeDE],
         [monitoringTypeDE],
         [First_Barrier_hit_DateDE],
         [currencyDE],
         [observationLevelPctDE],
         [BarrierDE],
         [price_closeDE],
         [price_dateDE],
         [Distance_dailyDE];
        """

        df = self.engine.read_sql(query, none_on_empty_df=True, params=((self.input_args.get("isin"), self.input_args.get("date"))))
         # Filter columns where all values are the same and non-NaN
        df = df.dropna(axis=1, how='all')
        df = self.apply_german_d3_formatting(df, 2)
        self.placeholders["table5"] = self.to_mdl_html(df)
        return



    def get_table6(self):
        query = """
SELECT TOP 50 [observationDateDE] AS [Investition],
           [displaynameDE] AS [Basiswert],
           [currencyDE] AS [Währung],
           [invested_partDE] AS [Investiert (%)],
           [obsfixingDE] AS [Investitionsfixierung],
           [observationlevelpctDE] AS [Level %],
           [BarrierDE] AS [Level],
           [Underlying_Last_PriceDE] AS [aktueller Kurs],
           [Pct_InitialFixingDE] AS [% zu Fixierung oder Level]
FROM clients.products_dropback_obs_hist
WHERE (isin = ?) AND (product_date = ?)
GROUP BY [observationDateDE],
           [displaynameDE],
           [currencyDE],
           [invested_partDE],
           [obsfixingDE],
           [observationlevelpctDE],
           [BarrierDE],
           [Underlying_Last_PriceDE],
           [Pct_InitialFixingDE]
ORDER BY 
            [observationlevelpctDE] DESC;
        """

        df = self.engine.read_sql(query, none_on_empty_df=True, params=((self.input_args.get("isin"), self.input_args.get("date"))))
         # Filter columns where all values are the same and non-NaN
        df = df.dropna(axis=1, how='all')
        df = self.apply_german_d3_formatting(df, 2)
        self.placeholders["table6"] = self.to_mdl_html(df)
        return











    def get_chart1(self):
        query = """
    SELECT TOP 10000 DATEADD(DAY, DATEDIFF(DAY, 0, price_date), 0) AS price_date,
               max(price_bid) AS [Geldkurs]
    FROM clients.products_price_history
    WHERE (isin = ?) AND (product_date = ?)
    GROUP BY DATEADD(DAY, DATEDIFF(DAY, 0, price_date), 0)
    ORDER BY [Geldkurs] DESC;
        """
        colors = ["#13294B", "#FDC600", "#A9C13F", "#0092D0", "#747476"]
        df = self.engine.read_sql(query, (self.input_args.get("isin"), self.input_args.get("date")))
        df["price_date"] = pd.to_datetime(df["price_date"])
        df.set_index("price_date", inplace=True)

        # Filter to last year's data
        #one_year_ago = datetime.now() - timedelta(days=165)
        #df = df[df.index > one_year_ago]

        # Sort the dataframe by date
        df.sort_index(inplace=True)

        fig, ax = plt.subplots(figsize=(9, 3))
        ax.plot(df.index, df["Geldkurs"], color="grey")


        # Hide spines
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color("grey")
        ax.spines["left"].set_color("grey")
    
        ax.yaxis.tick_left()
        ax.xaxis.tick_bottom()

        # Set tick color to grey
        ax.tick_params(axis='x', width=0.5, colors="grey")
        ax.tick_params(axis='y', width=0.5, colors="grey")
        plt.setp(ax.get_xticklabels(), rotation=45)
        
        # Change the x-axis color to grey and remove title
        ax.tick_params(axis="x", colors="grey")
        ax.set_xlabel("")
        
        
        ax.set_ylabel("Geldkurs")
        ax.grid(False)

        svg_io = io.StringIO()
        fig.savefig(svg_io, format="svg", bbox_inches="tight", pad_inches=0)
        plt.close(fig)
        svg_str = svg_io.getvalue()
        svg_io.close()
        self.placeholders["product_chart"] = svg_str
        return 









    def get_chart2(self):
        query = """
    SELECT TOP 10000 DATEADD(DAY, DATEDIFF(DAY, 0, price_date), 0) AS __timestamp,
            bbg_comp_ticker AS bbg_comp_ticker,
            max(price_close) AS [Schlusskurs]
    FROM clients.products_underlyings_price_history
    JOIN
    (SELECT TOP 5 bbg_comp_ticker AS bbg_comp_ticker__,
                max(price_close) AS mme_inner__
    FROM clients.products_underlyings_price_history
    WHERE (isin = ?) AND (product_date = ?)
    GROUP BY bbg_comp_ticker
    ORDER BY mme_inner__ DESC) AS anon_1 ON bbg_comp_ticker = bbg_comp_ticker__
    WHERE (isin = ?) AND (product_date = ?)
    GROUP BY bbg_comp_ticker,
            DATEADD(DAY, DATEDIFF(DAY, 0, price_date), 0)
    ORDER BY [Schlusskurs] DESC;
        """
        df = self.engine.read_sql(
            query, (self.input_args.get("isin"), self.input_args.get("date"), self.input_args.get("isin"), self.input_args.get("date"))
        )
        
        # passing False to hide the chart in generated report upon empty dfs
        if not len(df):
            self.placeholders["basiswert_chart"] = False
            return
        
        df["__timestamp"] = pd.to_datetime(df["__timestamp"])
        df.set_index("__timestamp", inplace=True)
        df.sort_index(inplace=True, ascending=True)
        
        fig, ax = plt.subplots(figsize=(9, 3))
        colors = ['#42546f', '#657426', '#98ae39', '#a1a9b7',
                  '#76872c', '#bacd65', '#d4e09f', '#fed74d',
                  '#515153', '#68686a', '#909091', '#acacad',
                  '#68686a', '#828284', '#acacad', '#c7c7c8',
                  '#111306', '#191400', '#000f15']
        
        color_cycle = itertools.cycle(colors)
    
        for ticker in df["bbg_comp_ticker"].unique():
            ax.plot(
                df[df["bbg_comp_ticker"] == ticker]["Schlusskurs"],
                label=ticker,
                color=next(color_cycle),
            )
    
        # Change the x-axis color to grey and remove title
        ax.tick_params(axis="x", colors="grey")
        ax.set_xlabel("")
        
        
        # Hide spines
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color("grey")
        ax.spines["left"].set_color("grey")
        ax.yaxis.tick_left()
        ax.xaxis.tick_bottom()
        
        plt.setp(ax.get_xticklabels(), rotation=45)
        
        # Set tick color to grey
        ax.tick_params(axis='x', width=0.5, colors="grey")
        ax.tick_params(axis='y', width=0.5, colors="grey")
    
        ax.set_ylabel("Preis (normalisiert auf 100)")
    
        # Remove grid
        ax.grid(False)
    
        # Create legend with no frame, at the top and in one line
        ax.legend(
            frameon=False,
            loc="upper center",
            bbox_to_anchor=(0.5, 1.05),
            ncol=len(df["bbg_comp_ticker"].unique()),
        )

        svg_io = io.StringIO()
        fig.savefig(svg_io, format="svg", bbox_inches="tight")
        plt.close(fig) 
        svg_str = svg_io.getvalue()
        svg_io.close()
        self.placeholders["basiswert_chart"] = svg_str
        return






    @staticmethod
    def to_mdl_html(df):
        if not isinstance(df, pd.DataFrame):
            return None
        html_table = df.to_html(index=False, classes="table-dataframe")
        html_table = html_table.replace(
            "<th>", '<th class="mdl-data-table__cell--numeric">'
        )
        html_table = html_table.replace(
            "<td>", '<td class="mdl-data-table__cell--numeric">'
        )
        return html_table

    @staticmethod
    def format_german(x, dec_places, grouping=True, decimal=True, percent=False):
        if isinstance(x, (int, float)):
            format_str = "{:,.%df}" % dec_places
            number = format_str.format(x).replace(",", "X")
            if decimal:
                number = number.replace(".", ",")
            else:
                number = number.split(".")[0]

            if grouping:
                number = number.replace("X", ".")
            else:
                number = number.replace("X", "")

            if percent:
                number = number + "%"

            return number

        if percent:
            x = x + "%"

        return x

    @staticmethod
    def apply_german_d3_formatting(df, dec_places=None):
        if not isinstance(df, pd.DataFrame):
            return None
        # Get numerical columns only
        ignore_columns = ["PA Nr.", "Datum (Kurs)"]
        no_decimal = ["Bestand", "Bestand (Eur)", "Bestand EUR"]       
        percent_columns = ["1 Tag", "seit Lancierung", "%Anteil", "participationMinDE", "participationMaxDE"]   
        num_cols = df.select_dtypes(include=np.number).columns.tolist()
        custom_decimal_places = {
            "Geldkurs": 2,
            "1 Tag": 2,
            "seit Lancierung": 2,
            "%Anteil": 2,
            "Kupon": 3,
            "Kupon Level %": 2,
            "participationMinDE": 2,
            "participationMaxDE": 2,
        }

        for col in num_cols:
            if col in ignore_columns:
                continue
            # Calculate maximum decimal places needed
            grouping = True
            max_digits = (
                df[col]
                .dropna()
                .apply(
                    lambda x: len(str(x).split(".")[0])
                    if "." in str(x)
                    else len(str(x))
                )
                .max()
            )
            if max_digits <= 5:
                grouping = False

            if col not in custom_decimal_places:
                if not dec_places:
                    maxdec = min(
                        df[col]
                        .dropna()
                        .apply(
                            lambda x: len(str(x).split(".")[-1]) if "." in str(x) else 0
                        )
                        .max(),
                        4,
                    )
                else:
                    maxdec = dec_places
            else:
                maxdec = custom_decimal_places[col]
            # Apply german d3 formatting to the column with dynamic decimal places
            df[col] = df[col].apply(
                Report.format_german,
                dec_places=maxdec,
                grouping=grouping,
                decimal=not col in no_decimal,
                percent=col in percent_columns,
            )

        df = df.fillna("")
        df = df.replace("nan%", "")
        df = df.replace("nan", "")
        return df
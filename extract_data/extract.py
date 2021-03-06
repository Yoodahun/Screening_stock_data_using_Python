import time
from datetime import datetime

import numpy as np
from requests.exceptions import SSLError

import extract_data.krx_condition as CONDITION
from .basic_factor_data.korean_market_factor_data import KoreanMarketFactorData
import OpenDartReader
from config.api_key import OPEN_DART_KEY
import pandas as pd


class Extract:

    def __init__(self):
        self.factor_data = KoreanMarketFactorData()
        self.dart = OpenDartReader(OPEN_DART_KEY)  # config/api_key.py에서 api key의 설정이 필요함.
        self.report_code = [
            '11013',  # "1분기보고서":
            '11012',  # "반기보고서":
            '11014',  # "3분기보고서":
            '11011'  # "사업보고서"
        ]

        self.indicators = [
            '유동자산',
            '부채총계',
            '자본총계',
            '자산총계',
            '매출액',
            '매출총이익',
            '영업이익',
            '당기순이익',
            '영업활동현금흐름',
            '잉여현금흐름'
        ]

        self.financial_column_header = ["종목코드", "연도", "시가총액"] + self.indicators

    def get_data(self):
        print(f"Getting data from KRX")
        pd.set_option('display.max_columns', None)

        df_kospi = self.factor_data.get_kospi_market_data()
        df_kosdaq = self.factor_data.get_kosdaq_market_data()

        return pd.concat([df_kospi, df_kosdaq])

    def extract_finance_data(self, finance_years, df):
        pd.set_option('display.max_columns', None)

        pd.options.display.float_format = '{:.2f}'.format

        data = []

        count = 1
        for row in df.itertuples():
            print(f"extracting {count}/{len(df)} {row[2]}...")
            count += 1
            for year in finance_years:
                # calling finance data using OpenDartReader
                dt = self.__find_financial_indicator(row[1], year)
                data += dt

            time.sleep(0.15)

        df_financial = pd.DataFrame(data, columns=self.financial_column_header)

        # calculating factor data
        df_financial = self.__calculate_indicator(df_financial)

        print("Join Data------------")
        return pd.merge(df, df_financial, left_on="종목코드", right_on="종목코드", how="outer")

    def __find_financial_indicator(self, stock_code, year):
        current_assets = [0, 0, 0, 0]  # 유동자산
        liabilities = [0, 0, 0, 0]  # 부채총계
        equity = [0, 0, 0, 0]  # 자본총계
        total_assets = [0, 0, 0, 0]  # 자산총계
        revenue = [0, 0, 0, 0]  # 매출액
        grossProfit = [0, 0, 0, 0]  # 매출총이익
        income = [0, 0, 0, 0]  # 영업이익
        net_income = [0, 0, 0, 0]  # 당기순이익
        cfo = [0, 0, 0, 0]  # 영업활동현금흐름
        #cfi = [0, 0, 0, 0]  # 투자활동현금흐름
        capex = [0, 0, 0, 0] #유형자산의 증가
        fcf = [0, 0, 0, 0]  # 잉여현금흐름 : 영업활동의흐름 - 유형자산의 증가

        market_cap = [0, 0, 0, 0]  # 시가 총액
        date_year = str(year)  # 년도 변수 지정

        no_report_list = ['035420', '035720', '036570', '017670', '251270', '263750', '030200', '293490',
                          '112040', '259960', '032640', '180640', '058850']  # 매출총이익 계산 못하는 회사들

        data = []
        record = []

        for j, report_name in enumerate(self.report_code):
            time.sleep(0.1)
            # 연결 재무제표 불러오기
            try:
                report = self.dart.finstate_all(stock_code, year, report_name, fs_div='CFS')
            except SSLError:
                report = self.dart.finstate_all(stock_code, year, report_name, fs_div='CFS')

            today = datetime.today().date()

            if year == today.year:
                if report_name == "11012" and today.month <= 8: #2분기
                    break
                if report_name == "11014" and today.month <= 11:  # 3분기
                    break
                if report_name == "11011" and today.month <= 12:  # 4분기
                    break

            if report is None:  # 리포트가 없다면
                pass

            else:
                condition1 = CONDITION.get_condition1(report)
                condition2 = CONDITION.get_condition2(report)
                condition3 = CONDITION.get_condition3(report)
                condition4 = CONDITION.get_condition4(report)
                condition5 = CONDITION.get_condition5(report)
                condition6 = CONDITION.get_condition6(report)
                condition7 = CONDITION.get_condition7(report)
                condition8 = CONDITION.get_condition8(report)
                condition9 = CONDITION.get_condition9(report)
                condition10 = CONDITION.get_condition10(report)
                condition15 = CONDITION.get_condition15(report)

                # 유동자산
                current_assets[j] = self.__check_index_error(report, condition1)
                # 부채총계
                liabilities[j] = self.__check_index_error(report, condition2)
                # 자본총계
                equity[j] = self.__check_index_error(report, condition3)

                # 매출액 계산
                if stock_code == '003550':  # LG의 경우, 매출이 쪼개져있으므로 매출원가 + 매출총이익을 더한다.
                    revenue[j] = self.__check_index_error(report, CONDITION.get_condition11(report)) + \
                                 self.__check_index_error(report, condition5)
                else:
                    revenue[j] = self.__check_index_error(report, condition4)


                #매출총이익 계산
                if stock_code == '011810':  # 매출총이익 항목이 없는 회사도 있다. 이 경우, 매출액 - 매출원가로 계산.
                    grossProfit[j] = revenue[j] - self.__check_index_error(report,
                                                                           CONDITION.get_condition11(report))
                elif stock_code in no_report_list:  # 매출총이익도 없고 이를 계산할 매출원가도 없다.
                    grossProfit[j] = 1
                elif stock_code == '008770':
                    grossProfit[j] = revenue[j] - self.__check_index_error(report,
                                                                           CONDITION.get_condition14(report))
                else:
                    grossProfit[j] = self.__check_index_error(report, condition5)

                #영업이익
                income[j] = self.__check_index_error(report, condition6)

                #당기순이익
                if stock_code == '008600':
                    net_income[j] = self.__check_index_error(report, CONDITION.get_condition12(
                        report)) - self.__check_index_error(report, CONDITION.get_condition13(report))
                else:
                    net_income[j] = self.__check_index_error(report, condition7)

                #영업활동 현금흐름
                cfo[j] = self.__check_index_error(report, condition8)
                #투자활동 현금흐름
                # cfi[j] = self.__check_index_error(report, condition9)
                #유형자산의 증가
                capex[j] = self.__check_index_error(report, condition15)
                #자산총계
                total_assets[j] = self.__check_index_error(report, condition10)

                if report_name == '11013':  # 1분기
                    date_month = '03'
                    date_day = 31  # 일만 계산할꺼니까 이것만 숫자로 지정

                elif report_name == '11012':  # 2분기
                    date_month = '06'
                    date_day = 30
                    cfo[j] = cfo[j] - cfo[j - 1]  # 현금흐름은 2분기부터 시작
                    # cfi[j] = cfi[j] - cfi[j - 1]  # 현금흐름은 2분기부터 시작
                    capex[j] = capex[j] - capex[j-1]

                elif report_name == '11014':  # 3분기
                    date_month = '09'
                    date_day = 30
                    cfo[j] = cfo[j] - (cfo[j - 1] + cfo[j - 2])
                    # cfi[j] = cfi[j] - (cfi[j - 1] + cfi[j - 2])
                    capex[j] = capex[j] - (capex[j-1] + capex[j-2])

                else:  # 4분기. 1 ~ 3분기 데이터를 더한다음 사업보고서에서 빼야 함
                    date_month = '12'
                    date_day = 30
                    revenue[j] = revenue[j] - (revenue[0] + revenue[1] + revenue[2])
                    grossProfit[j] = grossProfit[j] - (grossProfit[0] + grossProfit[1] + grossProfit[2])
                    income[j] = income[j] - (income[0] + income[1] + income[2])
                    net_income[j] = net_income[j] - (net_income[0] + net_income[1] + net_income[2])
                    cfo[j] = cfo[j] - (cfo[j - 1] + cfo[j - 2] + cfo[j - 3])
                    # cfi[j] = cfi[j] - (cfi[j - 1] + cfi[j - 2] + cfo[j - 3])
                    capex[j] = capex[j] - (capex[j-1] + capex[j-2] + capex[j-3])

                #잉여현금흐름
                fcf[j] = (cfo[j] - capex[j])

                # 날짜 계산
                date_day = self.__check_weekend(date_year, date_month, date_day)
                date = date_year + date_month + str(date_day).zfill(2)
                date_string = date_year + '-' + date_month + '-' + str(date_day).zfill(2)

                #각 분기별 마지막 영업일의 시가총액
                market_cap_df = self.factor_data.stock.get_market_cap_by_date(date, date, stock_code)

                try:
                    market_cap[j] = market_cap_df.loc[date_string]["시가총액"]
                except KeyError:
                    print(market_cap_df)
                    market_cap[j] = 0

                # TODO
                # market_listed_shares[j] = market_cap_df.loc[path_string]["상장주식수"]

                record = [stock_code, date_string, market_cap[j], current_assets[j], liabilities[j], equity[j],
                          total_assets[j],
                          revenue[j], grossProfit[j], income[j], net_income[j], cfo[j],
                          fcf[j]]


            data.append(record)
        return data

    def __calculate_indicator(self, df):
        df.sort_values(by=['종목코드', '연도'], inplace=True)
        print(df)

        # 분기별 PER
        df['분기 PER'] = np.nan
        # 분기별 PBR
        df['분기 PBR'] = np.nan
        df['PSR'] = np.nan
        df['GP/A'] = np.nan
        df['POR'] = np.nan
        df['PCR'] = np.nan
        df['PFCR'] = np.nan
        df['NCAV/MC'] = np.nan
        df['분기 ROE'] = np.nan

        status = ['영업이익 상태', '매출액 상태', '당기순이익 상태']
        three_indicators = ['영업이익', '매출액', '당기순이익']

        df_temp = pd.DataFrame(columns=df.columns)

        corp_ticker = df.loc[:, ["종목코드"]].drop_duplicates().values.tolist()

        for row in corp_ticker:
            if row is None:
                continue
            print(f"Calculating {row[0]} factor indicators")
            df_finance = df[df["종목코드"] == row[0]].reset_index()

            for i in range(3, len(df_finance)):

                # PER : 시가총액 / 당기 순이익
                df_finance.loc[i, "분기 PER"] = df_finance.iloc[i]['시가총액'] / (
                        df_finance.iloc[i - 3]['당기순이익'] + df_finance.iloc[i - 2]['당기순이익'] +
                        df_finance.iloc[i - 1]['당기순이익'] + df_finance.iloc[i]['당기순이익'])

                # PSR : 시가총액 / 매출액
                df_finance.loc[i, "PSR"] = df_finance.iloc[i]['시가총액'] / (
                        df_finance.iloc[i - 3]['매출액'] + df_finance.iloc[i - 2]['매출액'] +
                        df_finance.iloc[i - 1]['매출액'] + df_finance.iloc[i]['매출액'])

                # POR : 시가총액 / 영업이익
                df_finance.loc[i, "POR"] = df_finance.iloc[i]['시가총액'] / (
                        df_finance.iloc[i - 3]['영업이익'] + df_finance.iloc[i - 2]['영업이익'] +
                        df_finance.iloc[i - 1]['영업이익'] + df_finance.iloc[i]['영업이익'])

                # PCR : 시가총액 / 영업활동 현금흐름
                df_finance.loc[i, "PCR"] = df_finance.iloc[i]['시가총액'] / (
                        df_finance.iloc[i - 3]['영업활동현금흐름'] + df_finance.iloc[i - 2]['영업활동현금흐름'] +
                        df_finance.iloc[i - 1]['영업활동현금흐름'] + df_finance.iloc[i]['영업활동현금흐름'])

                # PFCR : 시가총액 / 잉여현금 흐름
                df_finance.loc[i, "PFCR"] = df_finance.iloc[i]['시가총액'] / (
                        df_finance.iloc[i - 3]['잉여현금흐름'] + df_finance.iloc[i - 2]['잉여현금흐름'] +
                        df_finance.iloc[i - 1]['잉여현금흐름'] + df_finance.iloc[i]['잉여현금흐름'])

                # ROE : 당기순이익 / 자본총계
                df_finance.loc[i, "분기 ROE"] = ((
                        df_finance.iloc[i - 3]['당기순이익'] + df_finance.iloc[i - 2]['당기순이익'] +
                        df_finance.iloc[i - 1]['당기순이익'] + df_finance.iloc[i]['당기순이익'])/ df_finance.iloc[i]['자본총계']) * 100



            # PBR : 시가총액 / 자본총계
            df_finance["분기 PBR"] = df_finance['시가총액'] / df_finance['자본총계']

            # GP/A : 최근 분기 매출총이익 / 자산총계
            df_finance["GP/A"] = (df_finance['매출총이익'] / df_finance['자산총계'])



            # NCAV/MK : 청산가치(유동자산 - 부채총계) / 시가총액
            df_finance["NCAV/MC"] = (df_finance['유동자산'] - df_finance['부채총계']) / \
                                           df_finance['시가총액'] * 100

            ## 부채 비율
            df_finance['부채비율'] = (df_finance['부채총계'] / df_finance['자본총계']) * 100

            ###영업이익 / 매출액 / 당기순이익 증가율
            df_finance['영업이익 증가율'] = (df_finance['영업이익'].diff() / df_finance['영업이익'].shift(1)).fillna(
                0) * 100
            df_finance['매출액 증가율'] = (df_finance['매출액'].diff() / df_finance['매출액'].shift(1)).fillna(0) * 100
            df_finance['당기순이익 증가율'] = (df_finance['당기순이익'].diff() / df_finance['당기순이익'].shift(1)).fillna(
                0) * 100

            ## 영업이익률 / 당기순이익률
            df_finance['영업이익률'] = (df_finance['영업이익']/df_finance['매출액']) * 100
            df_finance['당기순이익률'] = (df_finance['당기순이익']/df_finance['매출액']) * 100

            df_finance.sort_values(by=['연도'], inplace=True, ascending=False)

            ## 영업이익, 매출액, 당기순이익 확인 지표
            for i in range(len(status)):
                df_finance[status[i]] = np.nan
                df_finance.loc[
                    (df_finance[three_indicators[i]] > 0) & (df_finance[three_indicators[i]].shift(-1) <= 0),
                    status[i]
                ] = "흑자 전환"
                df_finance.loc[
                    (df_finance[three_indicators[i]] <= 0) & (df_finance[three_indicators[i]].shift(-1) > 0),
                    status[i]
                ] = "적자 전환"
                df_finance.loc[
                    (df_finance[three_indicators[i]] > 0) & (df_finance[three_indicators[i]].shift(-1) > 0),
                    status[i]
                ] = "흑자 지속"
                df_finance.loc[
                    (df_finance[three_indicators[i]] <= 0) & (df_finance[three_indicators[i]].shift(-1) <= 0),
                    status[i]
                ] = "적자 지속"

            ## 기존 데이터프레임 하단에 종목별로 정제데이터들을 붙이기.
            df_temp = pd.concat([df_finance, df_temp])

        ### reindexing columns and return
        return df_temp.reindex(
            columns=['종목코드', '연도', '시가총액', '분기 PER', '분기 PBR', '분기 ROE', 'GP/A', 'PSR', 'POR', 'PCR', 'PFCR',
                     'NCAV/MC']
                    + self.indicators
                    + ['부채비율','영업이익률', '영업이익 증가율', status[0], '매출액 증가율', status[1], '당기순이익률','당기순이익 증가율', status[2]]
        )

    def __str_to_float(self, value):
        """
        문자열로된 숫자를 소수점으로 변환.
        :param value:
        :return: float or integer
        """
        if type(value) is float:
            return value
        elif value == '-':
            return 0
        else:
            return int(value.replace(',', ''))

    def __check_weekend(self, date_year, date_month, date_day):
        """
        주말인지 아닌지를 판단.
        :param date_year:
        :param date_month:
        :param date_day:
        :return:
        """
        date = date_year + date_month + str(date_day)
        date_formated = datetime.strptime(date, "%Y%m%d")  # datetime format 으로 변환

        if date_formated.weekday() == 5:
            if date_month == '12':
                date_day -= 2  # 연말의 경우 2일을 뺀다.
            else:
                date_day -= 1  # 토요일일 경우 1일을 뺀다.
        elif date_formated.weekday() == 6:
            if date_month == '12':
                date_day -= 3  # 연말의 경우 3일을 뺀다.
            else:
                date_day -= 2  # 일요일일 경우 2일을 뺀다.
        elif date_formated.weekday() == 4 and date_month == '12':
            date_day -= 1  # 연말인데 금요일이면 1일을 뺀다.

        # 추석에 대한 처리
        if date_month == '09' and date_year == '2020':
            date_day -= 1
        elif date_month == '09' and date_year == '2023':
            date_day -= 3

        return date_day

    def __check_index_error(self, report, condition):
        """
        간혹가다가 리포트에서 값을 조회할 수 없는 회사들이 있음. 이럴때는 해당 컬럼값에 그냥 -1을 넣어주기로 에러 핸들링.
        :param report:
        :param condition:
        :return:
        """
        try:
            return int(report.loc[condition].iloc[0]['thstrm_amount'])
        except IndexError:
            return -1
        except ValueError:
            return -1

"""XBRL concept routes (us-gaap unless prefixed dei:).

Order inside each tuple is priority. A route is only used when its facts exist
at the required period; the chosen concept is recorded in lineage so every
value can be traced back to an accession number and filing date.
"""

REVENUE = (
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
    "SalesRevenueServicesNet",
    "RevenuesNetOfInterestExpense",
    "ElectricUtilityRevenue",
    "RegulatedAndUnregulatedOperatingRevenue",
)
OPERATING_INCOME = ("OperatingIncomeLoss",)
PRETAX_INCOME = (
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
)
INCOME_TAX = ("IncomeTaxExpenseBenefit", "IncomeTaxExpenseBenefitContinuingOperations")
INTEREST_EXPENSE = (
    "InterestExpense",
    "InterestExpenseNonoperating",
    "InterestExpenseDebt",
    "InterestAndDebtExpense",
    "InterestExpenseNet",
)
DA = (
    "DepreciationDepletionAndAmortization",
    "DepreciationAndAmortization",
    "DepreciationAmortizationAndAccretionNet",
)
DEPRECIATION = ("Depreciation", "DepreciationNonproduction")
AMORTIZATION = ("AmortizationOfIntangibleAssets",)
CFO = (
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
)
CAPEX = (
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireProductiveAssets",
    "PaymentsForCapitalImprovements",
    "PaymentsToAcquireOtherPropertyPlantAndEquipment",
    "PaymentsToAcquireOtherProductiveAssets",  # e.g. Verizon tags total capex here
)
EPS = ("EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted", "EarningsPerShareBasic")

CASH = (
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    "Cash",
)
# Debt building blocks (instants)
DEBT_TOTAL = ("DebtAndCapitalLeaseObligations", "DebtLongtermAndShorttermCombinedAmount")
DEBT_NONCURRENT = (
    "LongTermDebtNoncurrent",
    "LongTermDebtAndCapitalLeaseObligations",
    "LongTermDebtAndFinanceLeaseLiabilityNoncurrent",
)
DEBT_CURRENT_TOTAL = ("DebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent")
LTD_CURRENT = ("LongTermDebtCurrent",)
SHORT_TERM = ("ShortTermBorrowings", "CommercialPaper", "OtherShortTermBorrowings")
LTD_INCL_CURRENT = ("LongTermDebt",)
OTHER_DEBT = ("LongTermNotesPayable", "NotesPayable", "SeniorNotes", "ConvertibleNotesPayable",
              "LongTermLineOfCredit", "LineOfCredit", "SecuredDebt", "UnsecuredDebt")
EQUITY_PARENT = ("StockholdersEquity",)
EQUITY_TOTAL = ("StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",)
NCI = ("MinorityInterest",)
PREFERRED = ("PreferredStockValue", "PreferredStockValueOutstanding")
LIABILITIES = ("Liabilities",)
ASSETS = ("Assets",)

SHARES_COVER = ("dei:EntityCommonStockSharesOutstanding",)
SHARES_BS = ("CommonStockSharesOutstanding",)
SHARES_WAD = ("WeightedAverageNumberOfDilutedSharesOutstanding",)

DEBT_ALL = DEBT_TOTAL + DEBT_NONCURRENT + DEBT_CURRENT_TOTAL + LTD_CURRENT + SHORT_TERM + LTD_INCL_CURRENT + OTHER_DEBT

ALL_CONCEPTS = tuple(dict.fromkeys(
    REVENUE + OPERATING_INCOME + PRETAX_INCOME + INCOME_TAX + INTEREST_EXPENSE + DA + DEPRECIATION
    + AMORTIZATION + CFO + CAPEX + EPS + CASH + DEBT_ALL + EQUITY_PARENT + EQUITY_TOTAL + NCI + PREFERRED
    + LIABILITIES + ASSETS + SHARES_COVER + SHARES_BS + SHARES_WAD))

ALLOWED_FORMS = ("10-K", "10-K/A", "10-Q", "10-Q/A", "10-KT", "10-KT/A", "20-F", "20-F/A", "40-F", "40-F/A")
ANNUAL_FORMS = ("10-K", "10-K/A", "10-KT", "10-KT/A", "20-F", "20-F/A", "40-F", "40-F/A")

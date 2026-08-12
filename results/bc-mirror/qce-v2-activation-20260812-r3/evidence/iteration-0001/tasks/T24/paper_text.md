# EARNINGS EXTRAPOLATION AND PREDICTABLE STOCK MARKET RETURNS [∗] Hongye Guo [†]

## December 3, 2021

**Abstract**


The U.S. stock market’s return during the first month of a quarter correlates

strongly with returns in future months, but the correlation is negative if the

future month is the first month of a quarter, and positive if it is not. These effects

offset, leaving the market return with its weak unconditional predictive ability

known to the literature. The pattern accords with a model in which investors

extrapolate announced earnings to predict future earnings, not recognizing that

earnings in the first month of a quarter are inherently less predictable than in

other months. Survey data support this model, as does out-of-sample evidence

across industries and international markets. These results challenge the Efficient

Market Hypothesis and advance a novel mechanism of expectation formation.


Keywords: Announcements, Stock Returns, Behavioral Finance


JEL codes: G12, G14, G40


_∗_ Previously titled ‘Underreaction, Overreaction, and Dynamic Autocorrelation of Stock Returns.’

_†_ Department of Finance, The Wharton School, University of Pennsylvania. Email:
hoguo@wharton.upenn.edu. I thank Winston Dou, Itamar Drechsler, Nick Roussanov, Robert Stambaugh, and Jessica Wachter for invaluable guidance over the course of the project. I thank participants
of the 2019 Yale Summer School in Behavioral Finance and especially to the organizer, Nick Barberis,
for an excellent education on behavioral finance. I thank Nick Barberis, Jules van Binsbergen, John
Campbell, Sylvain Catherine, Alice Chen, James Choi, Vincent Glode, Marco Grotteria, Marius Guenzel, Xiao Han, Tim Landvoigt, Yueran Ma, Craig Mackinlay, Sean Myers, Cathy Schrand, Michael
Schwert, seminar participants in Acadian Asset Management, MFS Workshop (PhD poster session),
and Yale Behavioral Reading Group for helpful comments. All errors are mine.


Electronic copy available at: https://ssrn.com/abstract=3480863


# **1 Introduction**

Predicting stock market returns with past returns is famously difficult. Kendall and


Hill (1953) and Fama (1965) documented decades ago that serial correlations in stock


returns are close to zero. In his seminal work, Fama (1970) defines the weakest form


of the Efficient Market Hypothesis as that prices reflect all information in past prices.


This hypothesis appears to work especially well for the US aggregate market. Poterba


and Summers (1988) show, for example, that monthly market returns in the US have


a small, insignificant positive autocorrelation over a horizon of 12 months. The lack


of correlation between past and future market returns in the US is not only a widely


accepted statistical phenomenon, but also an emblem of market efficiency.


I document that the US market return in the first month of a quarter in fact strongly


correlates with returns in future months, with the correlation being strongly negative


if the _forecasted_ month is the first month of a quarter (i.e. January, April, July, and


October) and strongly positive if it is not. This result can be understood as a two-step


refinement of regressing one month’s return on past 12 months’ return. The first step


is to condition on the timing of the dependent variable. The market return in the


first month of a quarter is strongly negatively predicted by the return in the preceding


12 months, whereas the returns in the second and third months of the quarter are


strongly positively predicted by the past 12 months’ return. This distinction is already


strong, highly significant at the one percent level, but it becomes even stronger after


taking the second step—refining the independent variable. Specifically, among any 12


consecutive months, exactly 4 are first months of a quarter, and these 4 months are


especially useful for predicting future returns.


These first months of a quarter are special and important to investors because they


contain fresh earnings news. This is due to the nature of the earnings cycle in the


US. Take January as an example. At the end of the December, firms close their books


2


Electronic copy available at: https://ssrn.com/abstract=3480863


for Q4, and they announce Q4 earnings in January, February, and March. January


therefore contains the early earnings announcements and is the first time that investors


learn about the economy’s performance in Q4. February and March also contain a


sizable fraction of earnings announcements, but by that time investors have already


learned much about Q4. The first months of the quarters are famously known as the


“earnings seasons” among practitioners and receive heightened attention. Throughout


this paper, I refer to them as “newsy” months, as they produce fresh earnings news. I


call the other 8 months “non-newsy” months.


I hypothesize that the above pattern of market return predictability arises from im

perfectly rational investors who extrapolate newsy month earnings to predict earnings


in future months but fail to account for the inherent variation of such predictability


across these future months. Because earnings autocorrelate across multiple fiscal quar

ters, this practice of extrapolation is broadly correct. However, earnings announced in


the newsy months are more difficult to predict than those announced in other months.


This is because in the newsy months firms report on a new fiscal period, and these earn

ings naturally have lower correlation with past earnings. This lower correlation is the


concrete meaning of fresh earnings news. On the other hand, earnings in the non-newsy


months have higher correlation with the past. A rational investor should accordingly


predict with a time-varying parameter. However, if the investor fails to recognize this


variation and extrapolates with the average parameter value instead, then good news


in the past predicts negative surprises in future newsy months and positive surprises


in future non-newsy months. These predictable surprises then give rise to predictable


return reversal (continuation) in newsy (non-newsy) months. Furthermore, even as in

vestors naively extrapolate, their expectations will tend to shift more in newsy months,


making the returns in those months especially useful in predicting future returns.


Having stated my hypothesis, I test its immediate predictions. I start by showing


that the serial correlation structure of aggregate earnings, as measured by aggregate


3


Electronic copy available at: https://ssrn.com/abstract=3480863


return on equity (ROE), is indeed significantly lower in the newsy months. This evi

dence substantiates one premise of my hypothesis. I then show with survey data from


IBES that sell-side analysts indeed fail to account fully for this variation in earnings


autocorrelation, consequently leaving different types of predictability in earnings sur

prises through the earnings cycle. This evidence is uniquely useful because survey data


are direct measures of market expectations, albeit imperfect. Moreover, I show that


the predictable reversals in aggregate market returns do not occur until the earnings


seasons begin. This alignment in timing suggests that it is indeed the earnings sea

sons that drive the return predictability, as opposed to other quarterly fluctuations


unrelated to earnings announcements.


The return predictability results of this paper are motivated by, but not constrained


to, the time-series setting. In additional to predictions confirmed in the time series


setting, my theory also makes predictions about cross sections. In particular, the im

perfect extrapolation mechanism that I propose potentially applies to the cross sections


of industries and countries. Motivated by these natural extensions, I uncover a similar


return predictability pattern in the cross section of industry excess returns. [1] Contin

uation in the cross section of stock returns, as in Jegadeesh and Titman (1993), has


also been extensively studied. Unlike the weak continuation found in the US aggregate


market, momentum in excess stock returns is a much stronger and more robust effect


(e.g., Asness et al. (2013)), and the industry component is shown to drive a large frac

tion of it (Moskowitz and Grinblatt (1999)). This paper shows that the strength of the


continuation in the cross section of industry returns also varies over time. Similar to the


results found in the aggregate market, industry momentum is strong in the non-newsy


months but virtually non-existent in the newsy months. Moreover, this dynamic mo

mentum pattern is very strong in industries with tightly connected fundamentals and


1It technically also exists in the cross section of stock returns. The effect however operates entirely
through the industry components of these stock returns.


4


Electronic copy available at: https://ssrn.com/abstract=3480863


weak in loosely connected industries, as my theory predicts. Additionally, I find a sim

ilar pattern in country momentum (Moskowitz et al. (2012), Garg et al. (2021)), and in


country-industry momentum. This consistency across multiple contexts is remarkable


and not always seen in studies of return predictability. These cross-sectional results


not only expand the scope of this paper, but also provide important out-of-sample


evidence. [2]


I also note that it seems difficult to explain the return predictability results with


a risk-based framework. Presumably, in such a framework, after a good newsy month


the future newsy months would be safe, but the future non-newsy months would be


risky. Moreover, expected market returns implied by my results are frequently nega

tive, so consequently a risk-based explanation would imply that the stock market is


frequently safer than cash. However, common macro-based risk measures such as the


surplus consumption ratio (Campbell and Cochrane (1999)) do not vary strongly at


the monthly frequency, and even if they do, they are unlikely to be able to make the


stock market safer than cash. Therefore, the most natural explanation for the novel


predictability documented in this paper involves investors who make mistake. Such an


explanation likely resides in the area of behavioral finance.


Fama (1998) makes an important critique of behavioral finance, which is that in


this literature, return reversal and continuation appear about equally frequently, and


the evidence accords with the Efficient Market Hypothesis if viewed together. This


paper provides a response to this critique by predicting when return continuation and


reversal occur. The response is specific to the context of the earnings reporting cycle,


2The most common approach of out-of-sample analysis in the context of return predictability is
that in Mclean and Pontiff (2016) and Hou et al. (2018), which look at a signal’s performance after its
publication. This is by definition not something that one can run at the time of publication. Another
approach is that utilized by Jensen et al. (2021), which involves looking at a larger and significantly
different dataset, such as one consisting of different countries. Here, I am taking this second approach.
Incidentally, another concept of ‘out-of-sample’ involves removing look-ahead-bias in the parameter
estimation process. This is a point made by Goyal and Welch (2008) and is especially relevant to
time-series signals. I will address this important point later in my paper, but ‘out-of-sample’ has a
different meaning in their context.


5


Electronic copy available at: https://ssrn.com/abstract=3480863


but the latter is an important and universal aspect of the financial market that leads


to strong return predictability across multiple contexts. The evidence in this paper


together speaks in favor of a novel mechanism of expectation formation, which features


fundamentals extrapolation with a “representative parameter” in lieu of a correct,


time-varying parameter.


The rest of this paper is structured as follows: Section 2 relates this paper to the


existing literature. Section 3 describes my data. Section 4 demonstrates the key return


predictability results in US market returns. Section 5 provides intuition behind those


results, and it substantiates the intuition using fundamental data. Section 6 provides


a simple stylized model with closed-form solutions that qualitatively illustrate the


intuition in Section 5. Section 7 performs supplementary analyses to test my theory in


further depth. Section 8 discusses alternative explanations. Section 9 concludes.

# **2 Related Literature**


This study relates to various ares of existing literature, beyond the branch that directly


focuses on return autocorrelation. My theoretical framework relates to a large body


of work in behavioral finance that focuses on the notions of under-, and over-reaction,


which naturally lead to predictable return continuation and reversal. However, rela

tively few paper has a model that simultaneously features under- and over-reaction,


both of which are necessary for my purpose. Such a framework would be useful, as


it informs us under what circumstances should one observe under- rather than over

reaction. Barberis et al. (1998) is a prominent piece of early work that achieves this.


Starting with an earnings process that follows a random walk, they show that if in

vestors incorrectly believe that the autocorrelation structure of this earnings process


is dynamic—specifically, that the structure follows a two-state regime-switching model


featuring continuation and reversal—then they will overreact to news that seems to be


6


Electronic copy available at: https://ssrn.com/abstract=3480863


in a sequence, and underreact to news that seems not. My framework uses the oppo

site mechanism as that in Barberis et al. (1998). In my model, the autocorrelation of


earnings process is actually dynamic, but investors incorrectly believe it is constant.


It is worth noting that while the broader logic behind such a mechanism is rel

atively new in the literature, the paper is not alone in employing it. Specifically,


Matthies (2018) finds that beliefs about covariance exhibit compression towards mod

erate values in the context of natural gas and electric futures, as well as macroeconomic


forecasts. Wang (2020) documents autocorrelation compression in the context of the


yield curve. Behind our papers is a particular bounded-rationality mechanism where


investors’ limited cognitive capacity prevents them from fully exploring the hetero

geneity of a parameter, leading them to simply use a moderate representative value


instead.


This paper contributes to the literature on fundamentals extrapolation (Lakonishok


et al. (1994), Greenwood and Hanson (2013), Nagel and Xu (2019)). An important


mechanism behind extrapolative practices is diagnostic expectations (Bordalo et al.


(2019), Bordalo et al. (2020), Bordalo et al. (2021b) ). Investors who form expectations


diagnostically overestimate the probabilities of the states that have recently become


more likely, resulting in overall over-extrapolation. [3] In my framework, the level of


extrapolation is moderate and correct on average. However, the level is incorrect in


a specific month, as the earnings announced in that month will have either higher or


lower correlation with past earnings than expected. Under- and over-extrapolation


coexist in my framework. They are just targeting earnings of different months.


This paper relates also to work on predictable yet eventually surprising fundamental


changes, e.g. Hartzmark and Solomon (2013) and Chang et al. (2017). This line of


works shows that events that discretely yet _predictably_ break from the past, e.g. issuing


of large dividends or having seasonally high earnings, can still surprise investors and


3Diagnostic expectation has a psychological root, e.g. Bordalo et al. (2021a).


7


Electronic copy available at: https://ssrn.com/abstract=3480863


lead to positive excess returns on the corresponding firms. Extending this intuition


to the aggregate market, one can understand the earnings announcements early in the


earnings reporting cycles as trend breaking events, as the announced earnings have


discretely yet predictably lower correlation with past earnings. If investors also fail


to anticipate this drop, we will observe reversals of aggregate returns in the newsy


months. Hence, this line of literature is especially relevant to the reversal arm in the


dynamic serial correlation of the stock returns.


A feature of my model is that investors do not fully appreciate the correlation


between earnings revealed early and late in the earnings reporting cycle. Enke and


Zimmermann (2017) show in an experimental setting that subjects fail to discount


correlated news despite the simple setup and extensive instructions and control ques

tions. Fedyk and Hodson (2019) document that old ‘news’ on Bloomberg terminals—


especially ones that combine multiple sources and are not direct reprints—generates


overreactions in the abnormal returns of the associated stocks that are corrected in the


subsequent days. The continuation arm of my results shares this theme, even though


my results are on the aggregate level and over a longer horizon (monthly). [4] It is worth


noting that even though the literature of correlation neglect and predictable fundamen

tals can individually explain the continuation and reversal arms of the returns, having


a single explanation, i.e. parameter moderation, for both arms still adds meaningfully


to the behavioral finance literature.


This paper also falls into the broader literature that studies the interaction between


earnings announcements and stock returns (e.g., Beaver (1968), Bernard and Thomas


(1989), Bernard and Thomas (1990), Chen et al. (2020b), Johnson et al. (2020)). An


important piece of recent work in this area is Savor and Wilson (2016), which focuses


on weekly stock returns. The authors first confirm that stocks have high returns


4My framework and correlation neglect predict different forms of return reversal. This is discussed
in more details in Appendix A.


8


Electronic copy available at: https://ssrn.com/abstract=3480863


on earnings announcement-week (as in Beaver (1968)), and additionally show that


stocks that have high announcement-week returns in the past are likely to have high


announcement-week returns in the future. Among other things, the authors also show


that early announcers earn higher returns than late announcers, and firms that are


expected to announce in the near-term future have higher betas with respect to the


announcing portfolios. Overall, the authors make a convincing case that earnings


announcements of individual firms resolve systematic risks that have implications for


the broader market.


Instead of the risks and the mean (excess) returns associated with earnings an

nouncements, my paper focuses on the under- and over-reaction that are potentially


related to them, as well as the resulting lead-lag relation of stock returns. Also, in

stead of the returns of the portfolio that long the announcing firms and short the


non-announcing firms, I focus on the aggregate market returns or the industry-level


returns in excess of the market, neither of which strongly correlate with the spread be

tween the announcing and non-announcing portfolios. In addition to these high level


distinctions, specific differences in empirical results will be further discussed later in


Section 8.


This paper also relates to the broad literature studying the seasonality of stock


returns, documented by Heston and Sadka (2008) and extended by Keloharju et al.


(2016). This literature also studies the autocorrelation of stock returns, and makes


the point that full-year lags have especially strong predictive power, which is a distinc

tion of the _independent_ variable. The main point of my paper, however, is that the


predictive power of past returns is different according to the timing of the _dependent_


variable. Philosophically, Heston and Sadka (2008) and Keloharju et al. (2016) are


consistent with the notion of stationarity of stock returns, while my paper challenges


it—specifically, the notion that the autocorrelation coefficients depend on displacement


and not time. Again, specific distinctions will be further discussed in Section 8.


9


Electronic copy available at: https://ssrn.com/abstract=3480863


The portion of this paper studying the industry level returns relates to a large ac

counting literature studying the information transfer within industry. Foster (1981)


first documented that earnings announcements have strong impact on stock prices of


other firms in the same industry. Clinch and Sinclair (1987) confirm and extend this


result on a sample of Australian firms; Han and Wild (1990) and Hann et al. (2019)


confirm similar results using alternative measures of information; Han et al. (1989) and


Brochet et al. (2018) do so with alternative announcements. Related, the literature has


also documented that such learning is often imperfect and lead to predictable errors:


Ramnath (2002) documents that news announced by the first announcer in the indus

try positively predicts surprises in subsequent announcements in the same industry,


and argues that investors underreact to these first announcements; Thomas and Zhang


(2008) confirm this finding, but additionally point out that within the same industry,


the late announcers’ excess returns during early announcers’ announcements negatively


predict these late announcers’ own announcement excess returns. This suggests that


investors overreact to these early announcements. [56] My paper differs from this litera

ture on several aspects: It focuses on industry level excess returns as opposed to stock


level in the context of both the independent and the dependent variables. Also, the


frequency I focus on is monthly, as opposed to daily. Lastly, I am interested in both


intra-quarter and cross-quarter relations, as opposed to just the former. My paper


therefore provides additional value to the accounting literature.


5The two seemingly contradictory results both exist and are in fact quite robust in my replication.
Their appearance of conflict highlights the imprecision in using under/overreaction to describe return
predictability patterns. The two patterns can naturally be explained together with one story, which
is that investors correctly extrapolate information from these early announcers, but fail to distinguish
between industry level information, which they should extrapolate, and idiosyncratic information,
which thy should not.
6Figure 1 of Thomas and Zhang (2008) cleanly summarizes the variety of predictability in this
space.


10


Electronic copy available at: https://ssrn.com/abstract=3480863


# **3 Data**

In terms of data sources, in the US, my return data come from CRSP, accounting


data come from Compustat North America, and EPS forecast data come from IBES


Detail History (adjusted). These are common data sources used by a large number


of studies. There are two main sources of earnings announcement dates in the US:


Compustat and IBES. Both data sources have been individually used in major studies.


These announcement days often disagree, though the disagreements are usually small


and are mostly concentrated before December 1994 (see Dellavigna and Pollet (2009),


for instance, for a discussion). For my purpose, this source of discrepancy is unlikely


to make a difference, but out of an abundance of caution, I implement the algorithm in


Dellavigna and Pollet (2009), which combines the Compustat and the IBES announce

ment dates to form the best estimate of the actual announcement dates. [7] In the event


that the adjusted announcement date is the same as the IBES announcement date, I


also shift the date to the next trading date if the IBES announcement time is after


the market closure. This follows Johnson and So (2018a), who implement the same


algorithm.


Outside US, my stock level return data mainly come from Compustat Global. The


only exceptions are Canadian data, which come from Compustat North America. My


country level return data come from Global Financial Data (GFD). The reason why


I use two different data sources of returns is that GFD provides country level return


data with longer history, and Compustat provides the stock level data that I need for


industry level studies. Compared to those focusing on the US market, studies em

ploying global accounting data and global earnings announcement dates are in smaller


numbers. However, there are still many prominent papers (e.g. Asness et al. (2019),


7The algorithm is effectively 1) when the two sources differ use the earlier date and 2) when
they agree and the date is before Jan 1, 1990 shift the day to the previous trading date. Please see
Dellavigna and Pollet (2009) for further details.


11


Electronic copy available at: https://ssrn.com/abstract=3480863


Jensen et al. (2021)), from which two data sources emerge: Compustat Global and


Thomson Reuters Worldscope. I compared the two data sources. Both of them have


good coverage of annual accounting data, but Worldscope provides substantially better


coverage of quarterly and semi-annual accounting data than Compustat Global. Also,


Worldscope records about 2 times as many earnings announcements. These two fac

tors are especially important for my purpose. I therefore use Worldscope for my study.


I use exchange rate data from Bloomberg to convert foreign currency denominated


accounting data and stock returns into US dollar denominated ones.


In terms of specific variables used, in the US, I use ‘value-weighted average re

turn’ (vwretd) to represent aggregate market returns, and SIC code to represent in

dustries. I use ‘Report Date of Quarterly Earnings’ (rdq from Compustat) and ‘An

nouncement Date, Actual’ (anndats ~~a~~ ct from IBES) for earnings announcement dates,


‘Common/Ordinary Equity–Total’ (ceqq) for book value of equity, and ‘Income Before


Extraordinary Items’ (ibq) for earnings. Globally, I use item 5905 from Worldscope for


earnings announcement dates, item 1551 for earnings, and item 7220 for book value of


equity. [8]

# **4 Predicting the US aggregate market returns**


In this section, I first describe the earnings reporting cycle in the US and then demon

strate that the serial correlation in the US aggregate market returns varies strongly


within this cycle. For ease of expression, I first define three groups of months: “Group


1” contains January, April, July, and October, “Group 2” February, May, August, and


November, and “Group 3” March, June, September, and December. They are the first,


second, and the third months of quarters, respectively. In the US, I will call group 1


8It is useful to note that the data are obtained by directly querying the ‘wsddata’ and ‘wsndata’
tables of Worldscope. Using the Wharton Research Data Services’ web query forms to download the
data might result in incorrect exclusion of semi-annual accounting data (those keyed with freq of ‘S’).


12


Electronic copy available at: https://ssrn.com/abstract=3480863


months the “newsy” months. The reason that they are called newsy is they are when


_fresh_ news on firm earnings comes out _intensively_ . The news is fresh because group


1 months immediately follow the end of the fiscal quarters, the majority of which are


aligned with the calendar quarters. This is demonstrated in Table 1, which shows that


in the US, about 85% of fiscal quarters end in the group 3 months. Moreover, Table


2 shows that in the US, about half of the firms announce within one month after the


end of a fiscal period. In fact, among all of the three types of months, most firms an

nounce in group 1 months. Therefore, group 1 months are when fresh news is reported


intensively. The two features of freshness and intensity are the concrete meanings of


the word “newsy.” These newsy months largely correspond to the so-called ‘earnings


seasons’, which is a term frequently used by practitioners. The bottom line is that in


terms of the earnings news, in the US, group 1 months are the information-relevant


months.


Having understood why these group 1 months are special, we look at Table 3, which


reports results of the following monthly time-series regression that predicts the aggre

gate US stock market return: _mktt_ = _α_ + [�][4] _j_ =1 _[β][j][mkt][nm]_ [(] _[t,j]_ [)][ +] _[ϵ][t]_ [.] [Here] _[ mkt][nm]_ [(] _[t,j]_ [)] [is the]


_j_ th “newsy” month return strictly before the month _t_ . Unless otherwise noted, returns


on those newsy months are put on the right-hand side of the regressions throughout


my empirical analyses. Figure 1 thoroughly illustrates how lagging is done on the re

gression: Suppose the dependent variable is the return of November, then lag 1 newsy


month (abbrv. lag 1nm) return is that of October, lag 2nm return is that of July and


so on. As the dependent variable moves forward to December and January of the next


year, the lagged newsy month returns on the right-hand side stay the same. However,


when the dependent variable becomes the return of February, the lag 1nm return will


move forward by three months to January, as that is the most recent newsy month


strictly before February.


Having clarified the specifics of the regressions we move on to the results. Column


13


Electronic copy available at: https://ssrn.com/abstract=3480863


1 of Table 3 confirms the conventional view that the aggregate stock market exhibits


only weak momentum with a look-back window of one year. Column 2 does the same


regression, but only on the 1/3 of the sample where the dependent variables are returns


of the newsy months. This column shows that in newsy months, returns are decidedly


negatively correlated with past newsy month returns. Column 3 does the regression for


the rest of the sample, where the dependent variables are returns of non-newsy months.


In those months, returns are positively correlated with past newsy month returns.


However, on average they cancel each other out, resulting in the weak unconditional


predictive coefficients shown in column 1.


The main empirical finding of this paper is that the serial predictive relation in


stock returns varies by the timing of the dependent variable. Column 4 delivers this


main point by showing the difference in the coefficients of columns 2 and 3. While the


differences are not monotonic with lags, they are clearly all negative, and overall the


effect is stronger the smaller the lag. To evaluate the strength of the effect in different


contexts, such as different historical periods, it is useful to have one coefficient instead


of four. Throughout the empirical section, I use the sum of the first four lags, or

�4 _j_ =1 _[mkt][nm]_ [(] _[t,j]_ [)][,] [as] [the] [flagship] [signal.] [Since] [four] [lags] [correspond] [to] [the] [typical] [one-]


year look-back window of the various price momentum strategies, when I get to the


cross section this choice will enable me to benchmark against those strategies and speak


to when they work and don’t work.


Table 4 focuses on the following regression: _mktt_ = _α_ + _β_ [�] _j_ [4] =1 _[mkt][nm]_ [(] _[t,j]_ [)] [+] _[ϵ][t]_ [.] [Here]
�4 _j_ =1 _[mkt][nm]_ [(] _[t,j]_ [)] [is] [the] [sum] [of] [the] [lag] [1 to] [lag] [4] [newsy] [month] [returns,] [the] [said flagship]


signal. Its coefficient here roughly corresponds to the average of the first four coeffi

cients [9] in Table 3. Column 1 shows the weak unconditional time-series momentum,


pushed over the p-value cutoff of 5% by putting only the newsy month returns on the


right-hand side (regressing on the past 12-month return will result in a t-stat of 0.60).


9This approximate relation works for returns but not in general.


14


Electronic copy available at: https://ssrn.com/abstract=3480863


Column 2 and 3 are the subsamples for newsy months and non-newsy months returns.


Again we see strong negative predictive coefficients in newsy months and strong pos

itive coefficients in non-newsy months. The difference in the coefficients, -0.232, is


shown in the interaction term of column 4 with a t-stat of -4.93. These two values


indicate that in the full CRSP sample of 1926-2021, the serial predictive relation of the


US aggregate market return is strongly time varying. Columns 5-7 show that these


results are strong in the post-WWII period, first half, and second half of the sample,


though the effect is stronger in the first half of the sample.


Figure 2 compactly represents the results above. The red bars from left to right


show that market returns during past newsy months negatively predict returns in future


newsy months. The blue bars show that the relation flips if it is the non-newsy months


that are being predicted.


It is worth noting that because the predictor in the regression consists of newsy


month returns, when the dependent variable is newsy, it is further away from the


predictor in terms of calendar time. In column 2 of Table 4, the predictor is on average


7.5 calendar months away from the dependent variable. In column 3, the distance


is only 6 calendar months away. If return autocorrelation is greater the smaller the


calendar lags, then the difference of 1.5 months can potentially contribute the difference


between column 2 and 3 of Table 4.


To investigate the impact of calendar month lags on return autocorrelation, I per

form a multiple regression of monthly aggregate market returns on its 12 calendar


month lags. Figure 3 plots the resulting autoregressive coefficients. Notice that the


fitted line across the lags is almost horizontal, with a slope of -0.00062. This shows that


within the horizon of 12 calendar months—which is what is relevant for our regressions


in Table 4, there is little relation between the calendar lag and autocorrelation. A slope


of -0.00062 per lag, combined with a total difference of 1 _._ 5 _×_ 4 = 6 calendar month


lags, produces a product of -0.004. This is substantially smaller than the difference of


15


Electronic copy available at: https://ssrn.com/abstract=3480863


-0.232 shown in column 4 of Table 4.


Even though there isn’t an appreciable association between return autocorrelation


and calendar month lags, Figure 3 does show a positive autoregressive coefficient of 0.11


for the very first lag. This coefficient is in fact significant at the conventional 5% level.


One may then worry that perhaps this first lag in itself drives the results in Table 4.


To investigate whether this is the case, I run 10,000 simulations of AR(1) process with


the autocorrelation being 0.11, and then run the regressions in Table 4 on each set of


simulated sample of 1,136 monthly observations. Table 5 juxtaposes regressions done


on real data with those done on simulated data. Column 1-3 are regression results on


real data. Column 4-6 report averages of 10,000 regression coefficients, each of which


is computed on a simulated sample. Column 1 repeats the previously shown main


result, featuring a highly significantly negative coefficient of -0.232 on the interaction


term. Column 4 is the corresponding regression done on simulated data. Here we


instead observe a much smaller coefficient of -0.019 that is also not anywhere close to


significance on samples of the same size. This evidence suggests that the difference in


calendar lags does not drive my results.


One may still be curious on how the regressions behave if we simply use trailing


12 month returns as predictors, which holds the calendar lag constant, as opposed to


trailing four newsy month returns, which do not. Column 2 of Table 5 does exactly


that. Here we see that the results remain highly significant at 1% level, [10] even though


less significant than those in column 1. Column 3 breaks down the trailing 12 month


returns into the trailing 4 newsy month and the trailing 8 non-newsy month return. It


shows that while market return’s correlation with the past returns are generally lower


when the dependent variable is newsy, from the perspective of independent variable,


past newsy months are mainly responsible for this dynamic predictive relation. The


10It is worth mentioning the results in later sections also remain significant if we use trailing 12
month returns.


16


Electronic copy available at: https://ssrn.com/abstract=3480863


interaction term for the non-newsy months also gets a negative coefficient of -0.031,


which means that similar dynamic predictability pattern also exists with respect to past


non-newsy months. This relation, however, is weak. Consequently, the specification


in column 2 behaves like column 1, except with more noise in the predictor. As we


will see in the following sections, the proposed explanation for this pattern naturally


applies better to the newsy months.

# **5 Intuition and earnings predictability**

## **5.1 Intuition**


In the past section, we saw that aggregate stock market returns in newsy months have


lower correlation with past returns, and those in non-newsy months have higher corre

lation with past returns. This difference in correlation exists in multiple newsy month


lags. In this section, I first provide intuitions on the reasons underlying this return


predictability pattern, and then substantiate the premises behind these intuitions with


fundamentals data.


Consider the following narrative: suppose investors forecast earnings outcome in the


upcoming months based on past earnings. To fix idea, suppose that they have just ob

served positive earnings news in April from the announcing firms, and are (re)assessing


their forecasts in May, June, and July. Because earnings are positively autocorrelated—


which we will show in the next subsection—investors correctly think that earnings in


the upcoming months are also good. In fact, earnings announced in May and June are


_especially_ likely to be good. This is because the announcing firms in those months are


also announcing on Q1—perhaps Q1 is just a good quarter for everyone.


However, in July, earnings of Q2, a different fiscal quarter, will be announced. Since


earnings are positively autocorrelated across multiple fiscal quarters, the numbers in


17


Electronic copy available at: https://ssrn.com/abstract=3480863


July are still likely good, as Q2 and Q1 are only one fiscal quarter apart. However,


earnings announced in May and June are _zero_ fiscal quarter apart from that in April.


Therefore, compared to those in May and June, earnings in July are less likely to


resemble that in April. If investors fail to fully anticipate this _discrete_ drop in earnings


similarity, they will be disappointed in July. On the other hand, if they do not fully


realize that the earnings in May and June are going to be especially good, they will be


positively surprised in those months. [11]


To see why multiple lags can be significant in column 4 of Table 3, notice that if


investors only forecast earnings in the next 3 months, then only one newsy month lag


should be operative. If investors forecast more months ahead, say 6, then good news


back in January would have led to higher earnings expectations in May, June, and


July—assuming that these initial reactions are not fully reversed before these target


months. [12] These higher expectations are again correct in direction as earnings in May


and June is only 1 fiscal quarter apart from that in January. In July, the distance


becomes 2 fiscal quarters. If investors again treat this discrete drop in similarity as


gradual, then good news in January would also correspond to positive surprises in May


and June, and disappointment in July.


The story above narrates from the perspective of a given forecasting month. Piv

oting to a given target month, the equivalent intuition is that aggregate earnings an

nounced in the newsy months naturally have lower correlation with past earnings, since


announcers in those months are announcing on a new fiscal quarter. This makes the


11Thomson Reuters, which operates the IBES system, organize earnings forecasts with the ‘FQx’
labels, where FQ1 represents the closet fiscal quarter in the future for which the earnings have not
been announced. FQ2 represents the 2nd closet fiscal quarter, and so forth. After an early announcer
announce, say, in April, its next quarter earning—which is likely to be announced in July—will take
the label FQ1. Notice earnings that will be announced in May and June also have the label FQ1.
Those who participate in the Thomson Reuters’ system and also use the result of this announcement
to inform their future forecasts can potentially be nudged to think of May, June, and July together
by this shared label.
12This is an important assumption with an implication that I will verify with survey data: initial
surprises should correspond to predictable surprises in the target months, as opposed to be fully
corrected before the target months.


18


Electronic copy available at: https://ssrn.com/abstract=3480863


earnings in newsy months further away from past earnings in terms of fiscal time,


holding constant the distance in calendar time. [13] On the other hand, earnings in


non-newsy months have higher correlation with past earnings. Consider investors who


forecast next-month earnings using past earnings: If they treat the next month as an


average month, i.e., they do not sufficiently distinguish whether the next month is


newsy or non-newsy, then when past earnings have been good, in the upcoming newsy


months the investors are likely to be disappointed, and in the upcoming non-newsy


months they are likely to see positive surprises.


The behavior that I propose above can be compactly described as fundamentals


extrapolation with a representative parameter. In the language of under- and over

reaction, this behavior implies that investors overreact when forecasting the earnings


announced in future newsy months, and underreact when forecasting future non-newsy


months earnings. Additionally, those newsy months are very natural time for investors


to revise their forecasts of future earnings. Hence, the initial mis-reactions are likely


more concentrated in the newsy months themselves. As the forecasted earnings are


later announced, the initial misreactions get corrected, and return continuation and


reversal emerge. Not only do the newsy (non-newsy) month returns correlate neg

atively (positively) with past returns in general, they correlate especially negatively


(positively) with past newsy-month returns. This mis-reaction concentration feature


does not endogenously arise from my framework of representative parameter. It is


nonetheless an intuitive feature that the return data speak in favor of. I discuss how


to formally incorporate this feature in the modeling section.


13The distinction between fiscal and calendar time is illustrated in Figure 4. For example, focusing
on news in the lag 1 calendar quarter: when the forecasted month is group 1, the average fiscal time
between the news in the forecasted month and that in the past calendar quarter is 1 fiscal quarter.
When the forecasted month is group 2, the average distance shortens to 2/3 fiscal quarter, and for
group 3 it is only 1/3 fiscal quarter. Note this relation holds for more than one lagged calendar quarter.
The overarching message is that when investors are trying to forecast the earnings in the upcoming
months, past information is more/less timely the later/earlier in the earnings reporting cycle.


19


Electronic copy available at: https://ssrn.com/abstract=3480863


## **5.2 US fundamental news in calendar time**

In this subsection we map the intuition in the previous subsection to fundamental


data, and show that earnings announced early in the reporting cycle indeed have lower


correlation with past earnings.


First, I need a measure of the previously mentioned “earnings” for a given month,


and ideally without using return information: It would be the most helpful to explain


the pattern in stock returns without using stock returns. The measure I choose is


aggregate return on equity (ROE), which is aggregate quarterly earnings divided by


aggregate book value of equity on the universe of stocks that announce in a given


month. Notice that aggregate earnings themselves are non-stationary, and need to be


scaled by something. I follow Vuolteenaho (2002) to use book value of equity, which


could be thought of as a smoothed earnings measure over a long look-back window.


This is because of the “clean accounting assumption,” which holds reasonably well in


reality (Campbell (2017)). This measure echoes with the literature studying aggregate


earnings (e.g. Ball et al. (2009), Patatoukas (2014), Ball and Sadka (2015), Hann et al.


(2020)), which shows that aggregate earnings convey important information for the


economy. Overall, ROE is a simple and reasonable manifestation of earnings, with


which I can quantitatively illustrate the intuition in the previous section.


Having picked the specific earnings measure, I construct this measure for each


calendar month among all the firms that announce in the month. Column 1 of Table 6


performs a simple regression of aggregate ROE on the sum of aggregate ROE over


the past months, and the result is simple and easy to interpret: the coefficient is


significantly positive, indicating it is indeed reasonable for investors to extrapolate past


earnings to forecast the future. However, columns 2-3 show that there are important


complications underneath this simple result, which is that this extrapolation works


substantially less well when the forecasted month is newsy, and that it works much


20


Electronic copy available at: https://ssrn.com/abstract=3480863


better when the forecasted month is non-newsy. Column 4 demonstrates that this


difference is statistically significant. Panel A performs the regressions only on firms


with fiscal quarters aligned with calendar quarters and also timely reporting. This may


lead to the concern that this does not represent the real experience of investors, who


observe all announcements of all firms. Panel B-D include these other firms and show


that the result is qualitatively similar.


What if the investors do not consider the complications in column 2-4, and use


only the simple and static results in column 1? In that case, when past earnings are


good, you would see negative surprises in upcoming newsy months; in the non-newsy


months you would see positive surprises. When forecasting earnings of these newsy


months you overreacted in the past; in forecasting these non-newsy month earnings


you underreacted in the past.


Notice it is not quite accurate to simply say that people underreact to news in the


newsy months. If return continues over some horizons after the newsy months, one can


characterize investors’ initial reactions in the newsy months as underreactions. This


indeed seems to be the case if one look at horizons that are less than two months, but in


the third month the return reverses and the overall continuation weakens substantially.


Besides, the main point of this paper is the _difference_ in the return serial correlations


between newsy and non-newsy months, not the sum.


It is more accurate to say that reactions to news in newsy months contain both


under- and overreactions. Specifically, reactions to news about future newsy months


are overreactions, and will be met with surprises in the opposite direction in future


newsy months. On the other hand, reactions to news about future non-newsy months


are underreactions, and will be met with surprises in the same direction in future


non-newsy months. Notice this is not a simple underreaction or overreaction story,


but instead is a framework featuring one mechanism of imperfect extrapolation, from


21


Electronic copy available at: https://ssrn.com/abstract=3480863


which both under- and over-reaction arise. [14]

# **6 Stylized model**


In this section I build a stylized model to formalized the intuition stated in earlier


sections. I present the simplest model that gets to the most important feature of


the data which is that newsy month returns are being more negatively predicted by


past returns, relative to the non-newsy month returns. A feature of the data that I


leave out of the model is that the newsy month returns themselves are responsible


for positively and negatively predicting future returns. I discuss how to modify the


model to incorporate this feature at the end of the section. The model is inspired


by Guo and Wachter (2019). Consider an infinite-horizon discrete-time economy with


risk-neutral investors. Let _Dt_ denote the aggregate dividend at time _t_, and _dt_ = log _Dt_ .

Define ∆ _dt_ = _dt_ _−_ _bt−_ 1 = _dt_ _−_ (1 _−_ _ρ_ )( [�] _[∞]_ _i_ =0 _[ρ][i][d][t][−]_ [1] _[−][i]_ [).] [Here,] _[b][t][−]_ [1] [is] [an] [exponentially]


weighted moving average of past dividends. Assuming a stable payout ratio, dividend


and earnings will be tightly related. _bt−_ 1 then resembles a scaled version of book value


of equity, which is an accumulation of past retained earnings. The measure ∆ _dt_ then


mimics the ROE measure that I used in my previous analyses. While the relation is


not exact and involves major simplifying assumptions, this setup does lead to a simple,


closed-form solution. I choose this setup to balance the simplicity in the model and


the connection with my empirical analyses. [15]


Consider investors in month _t −_ _j_ who have just observed ∆ _dt−j_ . They, being rea

14This is also distinctive from a story of correlation neglect, which states that the overreaction is
in the second months of the quarters. The distinction is carefully discussed in Appendix A. Evidence
supporting correlation neglect is documented in Table A1.
15A simpler way to model this is to let ∆ _dt_ = _dt_ _−_ _dt−_ 1, or period over period dividend growth.
This is in fact a special case of my setup where _ρ_ equals 0. It leads to an even simpler model with
fewer state variables, and conveys very similar intuitions. The measure is however different from what
I use in the empirical section. Another way of modeling this is to literally model book value of equity
as the sum of past retained earnings. This approach does not lead to closed-form solutions.


22


Electronic copy available at: https://ssrn.com/abstract=3480863


sonably extrapolative, make an adjustment of _mδ_ _[j]_ [+1] ∆ _dt−j_ on their forecast of ∆ _dt_ +1.


Here _m_ represents the degree of extrapolation, and _δ_ _[j]_ [+1] the decay over time. Then,


assuming the changes made in each month are additive, it follows that investors’ fore
cast for ∆ _dt_ +1 is _m_ [�] _j_ _[∞]_ =0 _[δ][j]_ [∆] _[d][t][−][j]_ [at] [the] [end] [of] [month] _[t]_ [.] [Formally,] [let] [the] [investors]


believe:



∆ _dt_ +1 = _m_



_∞_


_δ_ _[j]_ ∆ _dt−j_ + _ut_ +1 (1)

_j_ =0



_iid_
_ut_ _∼_ _N_ (0 _, σu_ ) _,_ _∀t_ (2)


And more generally, for all _i ≥_ 1:



∆ _dt_ + _i_ = _m_



_∞_


_δ_ _[j]_ ∆ _dt_ + _i−_ 1 _−j_ + _ut_ + _i_ (3)

_j_ =0



_iid_
_ut_ _∼_ _N_ (0 _, σu_ ) _,_ _∀t_ (4)


In other words, the investors extrapolate an exponentially weighted moving average


(EWMA) of past cash flow growth. The decay parameter in the EWMA _δ_ and the

degree of extrapolation _m_ lie between 0 and 1. Denote _xt_ = [�] _j_ _[∞]_ =0 _[δ][j]_ [∆] _[d][t][−][j]_ [,] [so] [that]


investors expect ∆ _dt_ +1 = _mxt_ + _ut_ +1. Notice _xt_ +1 can be recursively written as:


_xt_ +1 = ∆ _dt_ +1 + _δxt_ (5)


This recursive relation does not involve the investors’ beliefs yet. Now given the


investors’ beliefs of future cash flow growth, it follows that they believe the following


23


Electronic copy available at: https://ssrn.com/abstract=3480863


process of _x_ going forward:


_xt_ +1 = ∆ _dt_ +1 + _δxt_ (6)


= _mxt_ + _ut_ +1 + _δxt_ (7)


= ( _m_ + _δ_ ) _xt_ + _ut_ +1 (8)


A similar relation applies beyond period _t_ + 1. Notice _m_ + _δ_ needs to be less than


1 for the process of _xt_ to be stationary in the investors’ minds.


While the investors use a constant extrapolation parameter _m_ in their beliefs, in


reality the process is driven by a dynamic parameter that takes values _h_ and _l_ in


alternating periods, where _l_ _< m < h_ :



∆ _dt_ +1 =








 _hxt_ + _ut_ +1 _,_ where _t_ is even


 _lx_ + _u_ _,_ where _t_ is odd



_lxt_ + _ut_ +1 _,_ where _t_ is odd



This reduced-form setup maps to the empirical ROE dynamics described in previous


sections. While such dynamics are caused by heterogeneity in reporting lag among firms


that share a persistent time component in earnings, I do not model this particular


mechanism. [16] Given this cash flow process in reality, _xt_ +1 actually follows the process:



_xt_ +1 = _δxt_ + ∆ _dt_ +1 =








 ( _h_ + _δ_ ) _xt_ + _ut_ +1 _,_ where _t_ is even


 ( _l_ + _δ_ ) _x_ + _u_ _,_ where _t_ is odd



( _l_ + _δ_ ) _xt_ + _ut_ +1 _,_ where _t_ is odd



Having set up the investors’ beliefs and how they deviate from reality, I now compute


the equilibrium valuation ratio, which requires solely the beliefs, and the equilibrium


equity returns, which require both the beliefs and the reality. Denote the current


dividend on the aggregate market _Dt_ . Let _Pnt_ be the price of an equity strip that


16In an alternative version of the model, I model the underlying quarterly earnings as a persistent
process and monthly earnings as quarterly earnings broken with randomness. This more realistic
approach delivers similar intuition as my baseline model, but not closed-from solution.


24


Electronic copy available at: https://ssrn.com/abstract=3480863


expires _n_ periods away. Define:



_Fn_ ( _xt_ ) = _[P][nt]_ (9)

_Dt_



We now show that _Fn_ ( _xt_ ) is indeed a function of _xt_, our state variable representing


past cash flow growth. Notice _Fn_ ( _xt_ ) must satisfy the following recursive relation:


_Fn_ ( _xt_ ) = _Et_ [ _rFn−_ 1( _xt_ +1) _[D][t]_ [+1] ] (10)

_Dt_


Where _r_ is the time discounting parameter of the investors. Conjecture _Fn_ ( _xt_ ) =


_e_ _[a][n]_ [+] _[b][n][x][t]_ [+] _[c][n]_ [∆] _[d][t]_ . Notice the relation _dt_ +1 _−_ _dt_ = ∆ _dt_ +1 _−_ _ρ_ ∆ _dt_ . This is key to a simple


solution in closed form. Substitute the conjecture back into equation 10 and take the


log of both sides:


_an_ + _bnxt_ + _cn_ ∆ _dt_ = log _r_ + _an−_ 1+( _bn−_ 1( _m_ + _δ_ )+( _cn−_ 1+1) _m_ ) _xt−ρ_ ∆ _dt_ +2 [1][(] _[b][n][−]_ [1][+] _[c][n][−]_ [1][+1)][2] _[σ]_ _u_ [2]

(11)


Which leads to the following recursive relation for _an_, _bn_, and _cn_ :


_an_ = _an−_ 1 + log _r_ + [1] 2 [(] _[b][n][−]_ [1][ +] _[ c][n][−]_ [1][ + 1)][2] _[σ]_ _u_ [2] (12)


_bn_ = _bn−_ 1( _m_ + _δ_ ) + _m_ (1 + _cn−_ 1) (13)


_cn_ = _−ρ_ (14)


Notice equation 14 along with the boundary condition of _b_ 0 = 0 implies the solution:


_bn_ = [1] _[ −]_ [(] _[m]_ [ +] _[ δ]_ [)] _[n]_ (15)

1 _−_ _m −_ _δ_ _[m]_ [(1] _[ −]_ _[ρ]_ [)]


And _an_ can be pinned down accordingly. Notice the sequence of _bn_ is a positive,


increasing sequence that approach a potentially large limit _[m]_ [(1] _[−][ρ]_ [)] [Intuitively speaking,]

1 _−m−δ_ [.]


when _xt_ is high, dividends growth is expected to be high in the future, and therefore


25


Electronic copy available at: https://ssrn.com/abstract=3480863


current valuation is high. [17]


Having solved for the valuation ratios of an equity strip that expires _n_ periods away,


we bring in the actual cash flow process to compute its return _Rn,t_ +1. For even _t_, notice


the log return needs to follow:



log(1 + _Rn,t_ +1) = log( _[F][n][−]_ [1][(] _[x][t]_ [+1][)]



)
_Dt_




_[−]_ [1][(] _[x][t]_ [+1][)] _Dt_ +1

_Fn_ ( _xt_ ) _Dt_



= _an−_ 1 _−_ _an_ + _bn−_ 1 _xt_ +1 _−_ _bnxt_ + _cn−_ 1∆ _dt_ +1 _−_ _cn_ ∆ _dt_


+∆ _dt_ +1 _−_ _ρ_ ∆ _dt_


= _an−_ 1 _−_ _an_ + _bn−_ 1(( _h_ + _δ_ ) _xt_ + _ut_ +1) _−_ _bnxt_ + ( _cn−_ 1 + 1)( _hxt_ + _ut_ +1)


= _an−_ 1 _−_ _an_ + ( _h −_ _m_ )( _bn−_ 1 + (1 _−_ _ρ_ )) _xt_ + ( _bn−_ 1 + (1 _−_ _ρ_ )) _ut_ +1


Similarly, for odd _t_, we have:


log(1 + _Rn,t_ +1) = _an−_ 1 _−_ _an_ + ( _l −_ _m_ )( _bn−_ 1 + (1 _−_ _ρ_ )) _xt_ + ( _bn−_ 1 + (1 _−_ _ρ_ )) _ut_ +1


Two points are worth noting: First, in returns there is an unpredictable compo

nent ( _bn−_ 1 + (1 _−_ _ρ_ )) _ut_ +1 that is completely driven by the unpredictable component


in cash flow growth. Cash flow growth therefore correlates positively with contempo

raneous returns. Since returns are largely unpredictable, this component accounts for


most of their variation. Second, there is a predictable component that takes alternate


signs. Hence, in the months where cash flow growth has high/low correlation with past


growth, as represented by _xt_, past cash flow growth positively/negatively forecasts the


return. Given the contemporaneous correlation between return and cash flow growth,


past returns would also positively/negatively forecast current return in the high/low


17The loading on ∆ _dt_ is _−ρ_ because there is a reversal effect, which can be understood by considering the extreme case of _ρ_ = 1. In that case, ∆ _dt_ equals _dt_, and this means that investors expect the
_level_ of the dividend to mean revert. Hence high dividend implies low dividend growth in the future,
and thereby leads to low current valuation. Notice the loading _−ρ_ does not change with _n_ and the
coefficients _bn_ can eventually have a much larger effect.


26


Electronic copy available at: https://ssrn.com/abstract=3480863


correlation months.


Notice that this simple model has a few counterfactual aspects. First, it predicts


that returns and cash flow surprises are very highly correlated. In the data they are


only weakly positively correlated. This is because investors extrapolate the entirety


of ∆ _dt_, which then feeds into _xt_ and drives valuation and return. A more realistic


framework would feature investors who understand that part of the realized cash flow


is purely transitory and correctly leave them out of the state variable _xt_ . I write down


such a model in Appendix B.1.


Second, the baseline model predicts that all past returns—whether they are newsy


month returns or not—negatively predict future newsy month returns and positively


predict non-newsy month returns. In the data this distinction is much stronger when


past newsy month returns are used to forecast future returns. Notice in Table 3 and


4 only the newsy month returns are used on the right-hand-side of the regressions.


This feature can be incorporated by letting the ∆ _dt_ in the _l_ realization periods go into


_xt_ with higher weights. The economic meaning of this modification is that investors


perform especially intensive expectation formation in earnings seasons. While this may


be an intuitive premise, it is a feature that does not arise naturally from the model


but rather needs to be added. A version of this model that incorporates this feature is


written down in Appendix B.2.

# **7 Additional Tests**

## **7.1 First week of the quarter and first quarter of the year**


In this subsection I present further evidence on the relation between the predictability


pattern of aggregate market returns and the earnings reporting cycle.


First, in my previous analysis I focused on monthly stock returns, and therefore used


27


Electronic copy available at: https://ssrn.com/abstract=3480863


the concept of newsy months. However, the period of intensive earnings reporting, or


the earnings season, does not start immediately on the first day of the newsy months.


In fact, among firms with fiscal periods aligned with calendar quarters, only 0.27%


of their earnings announcements occur within the first week (more precisely, the first


5 trading days) of the quarter. This is an order of magnitude lower than what an


average week contains, which is about 8% of the announcements. In contrast, the


second week in each quarter sees 2.93% of the announcements, which is on the same


order of magnitude as an average week. The reversal of market returns—if indeed


arising from these earnings announcements—should not exist in the first week of the


newsy months.


The left panel of Table 7 shows that this prediction is exactly true. While we have


seen that past newsy month returns negatively predicts the next newsy month return


(reproduced in column 1), the coefficient is close to zero in the first week of a newsy


month. This weak coefficient is shown in column 2. Consequently, excluding the first


week of the newsy months makes the reversal effect even stronger, as is in column 3.


The right panel of Table 7 shows that analogous patterns exist in other countries


according to their own earnings seasons. For each country, I determine the pre-season


period in the first months of the quarters by calculating the 0.5 percentile value of the


reporting lag for that country. This value is then rounded down to the closet trading


week to arrive at the length of the pre-season. For US, because the reporting is fast,


this value converts to one trading week, which is the length used in the US analysis


above. For the other countries reporting is slower, and the pre-season periods are often


longer, ranging from 1 to 3 weeks. Column 5 shows that the market returns of these


countries also do not reverse in their corresponding pre-season periods. In contrast,


column 6 shows that the reversal is quite strong immediately outside these pre-season


periods. This foreshadows the reversal arm of my global sample results, which I will


demonstrate in more details in Section 7.3.2. Overall, Table 7 shows that the dynamic


28


Electronic copy available at: https://ssrn.com/abstract=3480863


serial predictive relation in stock returns is indeed tied to the earnings seasons. This


piece of evidence speaks in favor of stories involving these earnings reporting cycles


and against those built upon other unrelated quarterly fluctuations.


In addition to the first week of each quarter, in the first quarter of each year we


may also expect a weaker pattern of dynamic serial correlation of returns. The reasons


are two-folded. First, in Q1 earnings reporting is substantially slower. The median


reporting lag in the first quarter of the US is 41 days, while that for the other 3


quarters is 30 days. This is because firms need to additionally conduct 10-K filing in


Q1, which takes resources that could otherwise be used for earnings announcements.


Hence, January is less newsy than the other 3 newsy months. Second, in Q1 there


are widespread tax related trading, which can potentially add unrelated movements to


aggregate returns. Both reasons can lead to a weaker effect in Q1 than in the other 3


quarters. Table 8 shows that this is true. Comparing column 1-3 to 4-6, we see that


in Q1 both the positive and negative arms of return predictability are weaker.

## **7.2 Evidence from survey data**


In this subsection I test my theory with survey data from IBES. In the model, investors


overreact when predicting earnings in the upcoming newsy months, and underreact


when predicting those in the upcoming non-newsy months. It therefore has a key


prediction, which is that past earnings surprises positively predict surprises in the


upcoming non-newsy months, and negatively predict those in the upcoming newsy


months.


To test this prediction, I use EPS estimates from IBES Detail History. IBES Sum

mary History conveniently provides firm level consensus estimates, which are IBES’s


flagship product. However, it cannot be used in this particular case because these


consensuses are struck in the middle of the month per Thomson Reuters’ production


29


Electronic copy available at: https://ssrn.com/abstract=3480863


cycle. [18] Since I use calendar month returns, I compute analogous consensus estimates


at month ends, so that earnings surprises in a given calendar month can be measured


relative to them. [19]


At the end of each month, each firm’s consensus EPS estimate for a given fiscal


period is computed as the median of the estimates that are issued in the past 180


days relative to the forecast date. For each analyst, only the most recent estimate is


included in this calculation. This horizon is chosen to reflect the methodology with


which the IBES consensus is computed. [20] The results of the analysis are qualitatively


the same with a wide range of look-back windows.


A firm’s earnings surprise in the announcing month is the announced earnings per


share subtract its consensus forecast at the end of the previous month, and then divide


by its stock price at the previous month end. I am adopting price as the scaling


variable as opposed to book value per share to align with the standard practice in


the literature that studies earnings surprises (e.g. Hartzmark and Shue (2018)). The


results are very similar if I instead use book value of equity per share. For each earnings


announcement that occurs in month _t_, I aggregate their surprise measures with market


cap weight to form the aggregate earnings surprise in month _t_, or _Supt_ . I then run time

series predictive auto-regressions on _Supt_, and importantly, I separate the sample by


whether the dependent variable is a newsy month, and examine whether the predictive


coefficients differ in the two sub-samples.


Table 9 shows that we indeed observe a significantly lower predictive coefficient


when the dependent variable is newsy. Column 1 shows that past surprises strongly


positively predict the eventual aggregate earnings surprise on average. Column 2 shows


18Specifically the Thursday before the third Friday of every month.
19Incidentally, the most frequently cited issue with IBES Summary—the practice of crude rounding
combined with splits (Payne and Thomas (2003))—is not necessarily a grave concern for our purpose
as we are looking at the aggregate data, and rounding errors cancel with each other if aggregated
across many firms.
20This is according to the user manual of IBES.


30


Electronic copy available at: https://ssrn.com/abstract=3480863


that this predictive relation is less positive in the newsy months. Column 3 shows that


it is much stronger in the non-newsy months. Column 4 shows that this difference


between newsy and non-newsy months is statistically significant. Column 5 shows that


this difference is especially strong if we use surprises in newsy months in the past to


predict future aggregate earnings surprises. These significant differences are consistent


with the key prediction of the model.


However, if the model is taken to be a literal model of survey data, we should not


just expect a substantially weaker coefficient in column 2—we should see a negative


coefficient, like in the regressions with aggregate market returns. We do not see this


negative coefficient, because the overall underreaction among the analysts, reflected


by a strongly positive coefficient in column 1, is an aspect that does not translate


into market returns—the aggregate market returns in the US are only very weakly


positively autocorrelated overall. This discrepancy suggests that the latency in the


survey expectations is not completely present in the actual expectations of the market,


and it is the latter that I model. A more realistic representation of survey expectation


is perhaps an average between the timely market expectation and a smoothed measure


of past expectations. In the wake of this modification, my model would generate this


overall underreaction in the survey data. It would still predict that this underreaction


is weaker in the newsy month, and Table 9 shows that this key prediction holds true.

## **7.3 Cross sectional analysis**


**7.3.1** **US** **cross** **section** **of** **industries**


The main intuition behind the theory is the follows: if a group of stocks are 1) tightly


and obviously connected in fundamentals, so that investors actively learn one stock’s


information from other another stock’s announcement and 2) sizable in number, so


that the group as a whole reports progressively along the earnings reporting cycle,


31


Electronic copy available at: https://ssrn.com/abstract=3480863


then earnings announced in the newsy months will correlate much less strongly with


past news, compared to earnings announced in the non-newsy months. Failure to see


this time-varying serial correlation structure of earnings will lead to the dynamic return


predictability pattern shown above.


While it is very natural to apply this story first to all stocks in the US economy,


it should additionally apply to the cross section of industry-level stock returns. Two


random stocks in each industry of a country are more connected with each other than


two random stocks drawn from the same country. An industry is therefore a smaller


economy except better connected. As discussed in Section 1, extensive intra-industry


information transfer during earnings announcements is well documented by the ac

counting literature (e.g. Foster (1981)). In this section, I test whether industry excess


returns, or industry returns subtracting the aggregate market returns, exhibit a dy

namic serial predictive relation similar to that in the aggregate market returns.


Table 10 shows the regression results of industry excess returns on past newsy month


industry excess returns. While the structure of this table looks similar to that of Table


3, it differs in two aspects: First, Table 10 is on an industry-month panel instead of a


monthly time series. Second, Table 10 uses industry excess returns as opposed to the


aggregate market returns. What is used in Table 3 is what is being subtracted from


the dependent and independent variables in Table 10.


Stocks data are taken from CRSP. In each cross section, I drop the small stocks,


defined as those with market cap below the 10th percentile of the NYSE universe.


Industry-level returns are market cap-weighted averages. All regressions in Table 10


require that there be at least 20 stocks in the industry-month. This filter is applied


because the theory requires a sizable group of stocks to be in an industry. I use the


stock’s issuing company’s four-digit SIC code as the industry classification variable,


and drop observations with a missing SIC code, or a code of 9910, 9990, and 9999,


which represent unclassified. The empirical results remain significant if smaller cutoffs


32


Electronic copy available at: https://ssrn.com/abstract=3480863


are chosen, even though they become weaker. This is discussed later in the section.


Column 1 shows that within a look-back window of about a year, or the first four


lags, the cross section of industry stock returns exhibits positive price momentum


on average. This contrasts the tenuous momentum effect found on the US aggregate


market. Similar to the results on the aggregate market, this momentum effect is entirely


concentrated in the non-newsy months, and even flips sign in the newsy months. This


is shown in columns 2 and 3. Column 4 shows the difference between the coefficients


in the newsy months and non-newsy months, and they are overall negative within four


lags, as predicted.


While the four-digit SIC code is a commonly used, natural industry classification


variable, the first two and three digits represent less granular “industry” classification,


known as “major group” and “industry group”. Table 11 examines whether the return


predictability pattern is robust to the choice of the industry classification variable.


Here I switch to the sum of the first four lags, as before. Across Panel A to C, the


serial predictive relation of industry excess returns is strongly different across newsy


and non-newsy months. Hence, this pattern is not sensitive to the specific level of


the industry classification. Unless otherwise noted, I use the four-digit SIC code to


represent industries.


Analogous to what is done in the time series section, Table 12 additionally verifies


this time-varying predictive relation of industry level excess ROE with a monthly panel


regression. As before, we see that past earnings predict future newsy month earnings


significantly less well, compared to future non-newsy month earnings. This difference


appears statistically stronger than the time-series one in Table 6, likely due to the large


number of industries that provide richer variations in earnings and substantially more


observations.


Cross sectional variation across industries provides us with an interesting testing


ground of our proposed theory. At the beginning of the section, I mentioned that my


33


Electronic copy available at: https://ssrn.com/abstract=3480863


story applies to groups of stocks that are sizable in number, and are tightly connected


in fundamentals. These lead to testable predictions, which are examined by Table 13.


Column 1 and 2 run this test on directly measured cash flow connectivity. I compute


covariance of normalized excess ROE for each pair of stocks in the same industry

quarter, compute the within industry average (weighted by the geometric average of


the market capitalization of the pair of stocks), and then take the trailing four quarter


average for each industry. Each cross section is then split between high connectivity


industries and low connectivity ones. Column 1 and 2 show that the dynamic return


predictability pattern in industry level excess returns is indeed stronger on the highly


connected industries, and weak on the low connectivity ones. Chen et al. (2020a)


documented a financial contagion effect that leads to large cash flow comovements


within industries. They documented that such effect is larger on industries that 1)


have higher entry barrier and 2) are more balanced between financially strong and weak


firms. Column 3-6 run the tests on the corresponding subsamples, and found that the


effect is indeed stronger on the more balanced and the harder-to-enter industries. The


last two columns run the regression separately on industries with a smaller and a larger


number of constituents. They show that the effect is larger on those larger industries,


as predicted.


Table 14 further demonstrates the importance of connected fundamentals by con

ducting placebo tests on superficial and fake “industries”, where no such connection


exists. Column 1 performs the regression on an industry consisting of stocks with SIC


codes of 9910, 9990, 9999, and missing values, which all represent unclassified. Despite


the shared SIC code values, the stocks are not actually similar to each others. Here, we


see no effect, as expected. Column 2 assigns stocks to “industries” based on randomly


generated “SIC codes”. Here we again see no effect, unsurprisingly.


A potential confounding effect to heterogeneity analyses of return predictability


in general is that return predictability is naturally more concentrated on “inefficient”


34


Electronic copy available at: https://ssrn.com/abstract=3480863


stocks and industries, such as those with low market capitalization, price, and volume,


because it is harder for arbitrageurs to take advantage of return predictability on


these stocks. While there is no consensus on how this notion of inefficiency should


be measured, market capitalization is a good place to start. It is worth noting that


among the sorting variables I use, within industry cash flow connectivity and balance


are not obviously related to industry capitalization. Entry cost and number of industry


constituents are in fact positively related to industry capitalization, and the inefficiency


story alone predicts _smaller_ effects on the harder-to-enter and the larger industries,


which is the opposite of what my theory predicts and the opposite of what the data


shows. The tests run in Table 13 are sharp tests, in that the predicted empirical pattern


is unlikely to rise from this other effect of heterogeneous “inefficiency”.


Throughout the paper, I have been using the notions of ‘newsy’ and ‘non-newsy’


months, which reflect a binary approach. In Section 7.1, we saw that this binary


approach is sometimes insufficient. Specifically, in the first quarter the reporting is


substantially slower, and consequently January is less newsy than the April, July, and


October. I then showed that the reversal in January and the continuation in February


and March are less strong, and this is consistent with the notion that January is less


newsy and February and March are newsier. This illustrates the potential usefulness


of a quantitative measure of ‘newsyness’, according to which one can form testable


predictions like this in a more general and systematic way.


The major source of time series variation in newsyness is the Q1 effect, which is


already explored in Table 8. [21] However, the cross industry setting provides interesting


heterogeneity in 1) reporting lags and 2) fiscal period end time. Concretely, if an


industry consistently reports slowly, then for that industry, the first months of the


21Another thing is the earnings announcements have become a few days slower in the last two
decades, potentially due to the Sarbanes–Oxley Act of 2002. The change is too small to have an
appreciable effect in my later analyses. The sample is also not quite long enough to establish a clear
effect.


35


Electronic copy available at: https://ssrn.com/abstract=3480863


quarters should be less newsy, and the second and third months newsier. If an industry


has a sizable fraction of the firms ending their fiscal quarter with the first month of


each quarter, then for that industry the _second_ months of the quarters can potentially


contain more announcers with fresh news, and hence become newsier. Below, I develop


a method to quantify the newsyness of a month and then run tests on the constructed


measures.


I model the unit newsyness of each earnings announcement as exponentially de

clining in reporting lag, with various half-lives. Specifically, let the lag be _x_ days,


_x_
then _unit_ _newsy_ ( _x_ ) = 0 _._ 5 _HL_, where _HL_ is the half-life parameter. For each month

reporting lag, I compute the product of this unit newsyness measure and the percentage


of earnings announcements with this lag, which is the number of earnings announce

ments with the lag, divided by the total number of announcements this quarter. I then


aggregate the product to the month level. Overall, if a month contains announcements


with shorter reporting lags, it will be newsier. If a month contains more earnings


announcements, it will be newsier. Lastly, I rescale to sum to 1 per quarter, and av

erage historical newsyness to the month of the year level. In doing so, I use only data


available in real time. Specifically, I use the expanding window averages.


To illustrate the effect of the half life parameter, Table 15 tablulates the Q2 newsy

ness on the US aggregate economy for the last cross section, i.e. it uses all historical


data. From the left to right, the half life in the measure increases from one day to sixty


days. When the half life is small, the newsyness vector is effectively (1, 0, 0), which is


my original binary approach which sets April as newsy and May/June as non-newsy.


As the half life increases, the vector becomes closer to (0.5, 0.5, 0), which is roughly the


fractions of earnings announcements within those months. This is because that as the


half-life increases, early and late announcers are being weighted increasingly equally.


Previously, I run the regression _exreti,t_ = _α_ + _β_ 1 �4 _j_ =1 _[exret][i,nm]_ [(] _[t,j]_ [)][+] _[β]_ [2][(][�] _j_ [4] =1 _[exret][i,nm]_ [(] _[t,j]_ [)] _[×]_


_It_ _[nm]_ ) + _β_ 3 _It_ _[nm]_ + _ϵi,t_ . Here _exreti,t_ is the value weighted return of industry _i_ in month _t_


36


Electronic copy available at: https://ssrn.com/abstract=3480863


in excess of the market. _exreti,nm_ ( _t,j_ ) is the value weighted average excess return of in

dustry _i_ in the _j_ th newsy month before month _t_ . Importantly, _It_ _[nm]_ is a dummy variable


indicating whether month _t_ is newsy. I incorporate the said quantitative measure in this


regression in two ways. First, I replace _It_ _[nm]_ with the quantitative newsyness measure


_Newt_ . A newsyness value of 1 predicts strong reversal as before, while a moderate value

of 0.8 predicts weaker reversal in month _t_ . Second, I replace [�] _j_ [4] =1 _[exret][i,nm]_ [(] _[t,j]_ [)][, which is]

the sum of the previous four newsy months, with _exret_ 12 _[nw]_ _i,t_ [=][ �] _j_ [12] =1 _[exret][i,t][−][j]_ _[·][New][i,t][−][j]_ [,]


which is a weighted average of past 12 monthly excess return of industry _i_, with newsier


months carrying higher weights.


Panel A of Table 16 shows the results with half lives of 3, 4, and 5 days. The effect


is strong under a wider range of half lives, but these are roughly where the effect is


the most pronounced. It is worth noting that these half lives are kept the same across


industries to enforce discipline in this exercise and avoid excessive data mining. These


half lives will also be used in exercises across countries and country-industries. Overall,


we see that both the continuation term and the reversal term are stronger than under


the binary specification. [22] This exercise is not only a way to obtain higher statistical


power, but also a meaningful auxiliary test that takes advantage of the heterogeneity


across industries.


**7.3.2** **Global** **aggregate** **markets**


**Global** **earnings** **reporting** **cycle** Having described the results in the US, we move


to the global data. In addition to new data on stock returns, other countries have


different earnings reporting cycles from the US and therefore can potentially provide


22Since it is important that we do not invoke look-ahead bias in our quantitative newsyness measure,
the exercise is done on the post-1973 sample, where the earnings announcement dates are available.
The improvement is clear in spite of the smaller, post-1973 sample, where industry momentum is in
fact a little weaker overall. This is possible because after 1973 we still have about 50 years of data,
and the effect of correctly setting the newsyness for each month across different industries greatly
outweighs the effect of a smaller sample.


37


Electronic copy available at: https://ssrn.com/abstract=3480863


meaningful out-of-sample tests of the theory. At least two sources of variations in the


earnings reporting cycles appear of interest. First, variation in reporting frequency,


specifically, a number of major countries require firms to report semi-annually instead


of quarterly. Second, variation in reporting lag, specifically, all major countries report


substantially slowlier than the US.


To look into the variations, I collect interim earnings announcement date, earnings,


and book value of equity from Worldscope. Even though this data source has sub

stantially better coverage of interim accounting data than Compustat Global, the data


start only in 1990s, and the coverage does not stabilize until 1998. This is substan

tially shorter history relative to the quarterly accounting data in the US, where stable


coverage begins in 1971. Perhaps this is in part why studies on the US market is more


abundant. I nonetheless draw lessons from this international dataset, as some patterns


can be sufficiently clear even on a short sample of 20 years.


In terms of the variation in reporting frequency, a country level tabulation exercise


on fiscal periods’ end months reveals that in those countries requiring semi-annual


reporting, comparable numbers of firms have Mar/Sep and Jun/Dec fiscal periods end.


Hence, the entire country still operates on a quarterly calendar, and first months of


each quarters are still the earliest time for the freshest news to come out. The theory


therefore applies to those countries as well. [23]


Regarding the variation in reporting lags, first, the right panel of Table 1 shows that


the fiscal quarters are also well aligned with the calendar quarters in the global sample.


Hence, news in group 1 months remains the freshest in the global data. However, the


reporting intensity is very different and can be used to generate some heterogeneity


in the right-hand-side variables in the global analysis. Table 17 shows that relative to


23The only exception here is Australia, where Jun/Dec fiscal periods are overwhelmingly more
common. However, overall country level momentum is weak in Australia, and it is hard to say that
the small reversal we see in Jan/Feb and Jul/Aug is lending support to my theory. I nonetheless
keep the country in my sample, since there is still a non-trivial portion of firms with Mar/Sep fiscal
periods.


38


Electronic copy available at: https://ssrn.com/abstract=3480863


the US, a much smaller fraction of the firms announce in the group 1 months in the


global sample. In contrast, group 2 months contain the largest fraction of announcing


firms—about 60%. Globally, it seems that both group 1 and group 2 months are viable


candidates for newsy months, as the former provide the freshest news and the latter


come with the most intensive reporting. Group 3 months, however, do not fall in


either category. In fact, the average reporting lag in the US is 37 days, which is a little


longer than one month; that for the international sample is 55 days, which is about


two months. [24] In other words, globally group 1 combined with group 2 months roughly


constitute the first half of the earnings reporting cycles. To enforce consistency across


the US and the global analysis, I set the newsy “months” to be the combined periods of


group 1 and group 2 months in the global data. For example, April and May combined


is considered to be a newsy ‘month’ in the global data. [25]


It is important to note while the practice of setting ‘newsy’ months based on ag

gregate data is similar to what I did in the US, doing so on the global sample involves


a stronger assumption. In both the US and the global sample, the return data start


substantially earlier than the accounting data from which the newsy months are in

ferred. However, the history of accounting data is much longer in the US, and it can be


seen that over the course of this longer history the aggregate reporting cycle remained


stable, and in fact was a few days faster in the earlier decades. Also, it is clearly


documented that quarterly reporting has been present in the US even years before


1926 thanks to the requirements of the NYSE (Kraft et al. (2017)). Outside the US


similar evidence is less easy to find systematically in one place, [26] even though country

24Both numbers exclude cases where the lag exceeds 182 days. These cases have heightened probability of data errors. They are rare anyway.
25Finland is the only country other than the US to have an average reporting lag of less than 6
weeks. Setting group 2 months as non-newsy for Finland and newsy for all other non-US countries
indeed leads to slightly stronger results, but since this logic turns on for only one country it is too
sparse a source of variation. For the sake of simplicity I do not do this in my baseline analyses. Rather,
I more thoroughly utilize the variation in reporting lags across countries in the form of quantitative
newsyness in later analyses.
26It is very easy to find each country’s current reporting convention, but that can be seen in the


39


Electronic copy available at: https://ssrn.com/abstract=3480863


by-country research clearly shows that regular financial reporting has been on going


decades before the inception of the Worldscope data, at least for financially developed


nations like UK, Japan, France, and Australia.


Given these contexts, while I still use return data before 1990s in my global tests, I


focus on the financially developed countries, where financial regulation is sounder and


has longer history. The list of developed markets that I use follows that in Asness


et al. (2019) and consists of the developed markets classified by Morgan Stanley Cap

ital International (MSCI). Also, on this long sample of returns I only use the simplest


and most obvious message from the global earnings announcement data, specifically


which months are the newsy months. Analyses that take advantage of finer variations


in the earnings reporting cycles across countries are done on the post-1998 sample, and


are implemented so that the independent variable does not incur any look-ahead bias,


similar to what was done for the US industries. Even with these practices, one should


perhaps place more focus the post-war and the post-1974 results for the global sample,


and interpret the pre-1974 results with more caution.


**Global** **fundamental** **news** On the global panel of countries, analysis of the earnings


predictability supports the newsy status of group 2 months in the global data. Table


18 does similar regressions to those in Table 6, except it is now at a country-month


level. Because an average country has much smaller sample size than the US, the


country-month level ROE is winsorized at the 10th and the 90th percentiles of each


cross section to limit the impacts of the outliers caused by low aggregate book values


of equity. [27] The regressions are weighted by aggregate book value of equity of the


country-month divided by the total book value of the year. This regression weight


accounting data anyway.
27These rather deep winsorization bounds are necessitated by the small cross sections early in the
sample: those are precisely where the raw ROE values are extreme (due to small number of stocks in
the aggregation), and the cross section sizes are less than 20 countries—which means winsorzation at
the 5th and 95th percentiles makes no difference.


40


Electronic copy available at: https://ssrn.com/abstract=3480863


mimics that in Hartzmark and Shue (2018). It overweights large country-months and


at the same time does not mechanically overweight more recent cross sections. Overall,


Table 18 shows similar results to those in Table 6, which is past earnings predicts fu

ture earnings substantially less well in the newsy months, which are now first and the


second months of each quarters. The results are again robust to the inclusion of firms


that have fiscal quarters unaligned with calendar quarters and those reporting late.


**Return** **predictability** Having described the earnings-related information globally, I


move to the return predictability results. My country-level market returns come from


Global Financial Data (GFD). Returns are all in US dollar. A number of return series


go back further than 1926, but in this analysis I cut the sample at 1926 to be consistent


with the US results. [28] Of course, if the data for a certain country do not go back further


than 1926, the truncation is not operative for that country.


To start, Table 19 runs analogous regressions as those in Table 4, except they are


now on a panel of country level aggregate returns, and that the newsy months now


include both the first and the second months of each calendar quarter. In column 1,


we observe an unconditional momentum effect. This reflects country-level momentum


in Moskowitz et al. (2012), which is in fact stronger in more recent periods. Columns 2


and 3 then show that this component is much stronger in the non-newsy months, here


meaning the third months of the quarters. The results are robust in the post-war and


the post-1974 sample. The result is very weak in the first half of the sample, however,


perhaps reflecting the smaller sample size before 1974.


Since aggregate returns in other countries are going to be positively related to the


US market return contemporaneously, to observe the additional effect more cleanly, I


remove each country’s loading on the US market return according to their US return


28After deleting some obviously problematic data in the UK in the 1600s and 1700s, inclusion of
those early samples makes the results stronger.


41


Electronic copy available at: https://ssrn.com/abstract=3480863


betas. I estimate the betas on a rolling 24 month basis up to one month before the


dependent variable month, so that the beta does not contain any look-ahead bias,


and the dependent variable corresponds to positions implementable in real time. The


results are in Table 20, and they convey similar messages as those in Table 19.


In panel B of Table 16, I conduct an exercise involving quantitative newsyness, as


in the cross section of US industries. Here the analysis starts only in 2000, which leads


to a very small sample size. On this small sample, we do observe marginally significant


results, and somewhat larger effect. However, because of the small sample size one


needs to interpret these results with caution.


**7.3.3** **Global** **cross** **sections** **of** **industries**


Similar to the analyses for the US, I look at the cross sections of country-industry


returns in excess of the corresponding country-level returns. Returns are mostly taken


from Compustat Global, augmented with the Canadian stocks from Compustat North


America. To be consistent with the global aggregate market results, I constrain the


sample to the same list of countries in the previous section. Returns are winsorized at


the 0.5 and the 99.5 percentiles each cross section to limit the impact of absurdly large


values which are likely erroneous. [29] All returns are in USD. In each country-month,


10% of the smallest stocks are dropped, after which the returns are aggregated to the


industry and market level using market cap weight. The difference of those two returns


are then taken to arrive at the excess returns that I use. Here, I again require each


country-industry to have at least 20 stocks, consistent with the rest of the paper.


Table 22 shows similar patterns to those found in Table 11: Country-industries


exhibit momentum only in the non-newsy months. The results do not seem to be


sensitive to the particular choice of industry variable. Table 21 is the companion results


29This step may appear non-standard from the perspective of the US sample, but the reason is
that CRSP’s pricing data quality is unusually good. On a global sample the winsorization step or
operations that achieve similar ends are unavoidable. See, for instance, Jensen et al. (2021)


42


Electronic copy available at: https://ssrn.com/abstract=3480863


from earnings. It again demonstrates the strong variation in earnings’ correlation with


the past earnings. Like those in the US, the cross sectional piece of the earnings


regression produce statistically stronger difference than the time series piece. Despite


the very short sample that start in 1998, the difference is quite significantly established,


thanks to the large number of industries that provides rich cross sectional variation in


the data.


In panel C of Table 16, I again conduct an exercise involving quantitative newsyness


as before. Here the analysis again starts only in 2000, which again leads to a small


sample size, even though the cross sections of industries help to improve things relative


to the analyses on global market excess returns. We observe improvements and results


significant at the traditional level. Because of the small sample size we again need to


interpret these results with caution.

# **8 Alternative Explanations**


**Firms** **endogenously** **changing** **their** **reporting** **latency** A large literature in ac

counting examines the relation between the timing of firms’ earnings announcements


and the news they convey. A clear empirical pattern that emerges is that early an

nouncers tend to announce better news than late announcers (e.g. Kross (1981), Kross


and Schroeder (1984), Chambers and Penman (1984), Johnson and So (2018b), Noh


et al. (2021)). The literature has also extensively studied the reasons behind this pat

tern, and has partially attributed it to firms’ endogenous choices of reporting lag. For


instance, deHaan et al. (2015) argue that firms delay earnings announcements with


bad results to avoid the early portion of the earnings reporting cycle which receives


heightened attention. Givoly and Palmon (1982) argue that they do so to buy time so


that they can manipulate their accounting results.


However, it is not clear how this empirical regularity alone speaks to my results.


43


Electronic copy available at: https://ssrn.com/abstract=3480863


Overall, they imply that early announcers announce better results than late announc

ers. If investors fail to anticipate that, then early announcers will have higher earnings


surprises and higher announcement excess returns. It is not clear why it would cause


the market return early in the announcement cycle to positively correlate with that


late in the earnings reporting cycle. If anything, exogenous variation in the intensity of


this self-selection effect seems to lead to a negative correlation of early announcement


returns and late announcement returns within quarter, as bad announcers being moved


out of the newsy months makes the newsy months look better and the subsequent non

newsy months look worse than they otherwise would do. And even then it is not clear


why this return predictability pattern would extend across quarters.


**Predictability** **reflecting** **predictable** **resolution** **of** **risks** The most important


set of explanations for return predictability come from predictable resolution of risks,


which leads to high expected returns, as well as going through predictably low risk


periods, which leads to low expected returns. The type of variation in risks that is


necessary to explain my time series results is that after a good newsy month, the stock


market is very risky in the upcoming non-newsy months, and very safe in the upcoming


newsy months. This requires the risk of the market to vary at the monthly frequency.


The variation needs to have a dependency up to four quarters away, and it needs to


have a mixture of positive and negative dependence on the past, with the sign of the


dependence going from positive to negative, and then back to positive, and so on.


Standard asset pricing models such as habit, long-run risk, disaster, and intermediary

based asset pricing all involve risks that should be fairly persistent at the monthly


frequency. Even if they do vary, it is unlikely that the variation would cause its de

pendency on the past to take alternate signs across months. So it does not appear


appropriate to use them to explain my predictability pattern. A potentially more


hopeful candidate is those exploring the risk resolution that are associated with earn

44


Electronic copy available at: https://ssrn.com/abstract=3480863


ings announcements. Empirically, Savor and Wilson (2016) show that early announcers


earn higher excess returns than later announcers, which is indeed consistent with the


overall importance of the earnings season. This, however, does not explain why cur

rent earnings season being good makes future earnings seasons safer and future months


out of earnings seasons riskier. The authors also show that stocks with high past an

nouncement return in excess of the market earn higher returns during their upcoming


announcement weeks than those with low past announcement excess returns. The au

thors argue that this shows that the level of risks resolved by a given stock’s earnings


announcement is persistent. The authors also show that earnings announcement dates


are highly stable, and therefore firms that have announced in January are likely to an

nounce in April. Combining these two pieces of information, it may seem that returns


3/6/9/12 months ago might be influencing part of my cross sectional results. However,


apart from the difference in return frequency (monthly versus weekly) and cross sec

tional unit (industry/aggregate versus stock), observe that the excess returns 3/6/9/12


months ago are used only when the dependent variables are the newsy months, which


is a sub-sample where the coefficient in my regression is low, not high.


**Loading** **on** **the** **seasonality** **effect** My cross sectional results might seem related


to those in Heston and Sadka (2008) and Keloharju et al. (2016), who show that the


full-year lags, i.e., the 12, 24, 36, etc. monthly lags have unusually high predictive


coefficients on stock-level excess returns. Since their signals have no time-series varia

tion (i.e. stock returns in excess of the market have zero mean cross section by cross


section), the results cannot be related to my time-series results. However, could they


explain my industry level results? Full-year lags are indeed used in some of my regres

sion results. Specifically, they are part of the RHS when the dependent variable are


the group 1 months, like in column 2 of Table 10. However, observe that the point


of my paper is that in group 1 months the return predictive coefficients are unusually


45


Electronic copy available at: https://ssrn.com/abstract=3480863


low, exactly the opposite of the points made in the return seasonality literature. In


other words, my results exist in spite of the loading on return seasonality, not because


of it.


**Fluke** **driven** **by** **a** **small** **number** **of** **outliers** One may worry that the time-series


result is driven by a handful of outliers, and is therefore not very robust. To mitigate


this concern, I perform the regression in Table 4 by decades, and report the results in


Table 23. A few things come out of this exercise. First, the pattern is very strong in


the pre-1940 era, which can already been inferred from the post-war column of Table 4.


Second, in each and every decade, the coefficient on the interacted term is negative


and economically sizable. This shows that the effect is in fact quite robust across time


and not solely driven by short episode like the pre-1940 era. Lastly, we see that this


effect is by no means dwindling over time. In fact, in recent decades the dynamic serial


correlation pattern of the US market return is stronger. This shows that this effect is


not just a piece of history, but rather an ongoing phenomenon.


**Driven by look-ahead bias in estimated coefficient** Past research has cast doubts


especially on the practicality of time-series strategies in the stock market. Specifically,


Goyal and Welch (2008) show that in forecasting future stock market returns, predictors


combined with expanding window coefficients extracted without look-ahead bias fail to


outperform the expanding window mean of past market returns. While Campbell and


Thompson (2008) quickly show that imposing some simple and reasonable constraints


on the regression estimation process will make the predictor-based approach clearly


superior, it is nonetheless useful to make sure that the predictor in this paper can


generate positive _R_ [2] without involving coefficients estimated with look-ahead bias.


To investigate the _R_ [2] generated with no look-ahead bias coefficients, I extend the


CRSP aggregate market return series to 1871 using GFD data. I take valuation ratios


46


Electronic copy available at: https://ssrn.com/abstract=3480863


data from Robert Shiller’s website, and construct payout ratios and ROE series with


data from Amit Goyal’s website. These are used to generate the long-run return


forecasts as in Campbell and Thompson (2008). While the estimation sample go back


to 1872, the _R_ [2] are evaluated starting from 1926, consistent with what is done in


Campbell and Thompson (2008).


The monthly _R_ [2] generated by various estimation methods are reported in Table 24.


Coefficients are either constrained to be 1 or generated with simple expanding-window


OLS estimations. No shrinkage procedure is applied at all. In method 1, we see that


even the most naive method—combining signal with regression coefficients of returns on


past signals and a freely estimated constant—generates an _R_ [2] of 3.65%. This positive


_R_ [2] along with those generated with methods 2-7, should mitigate the concern that the


strategy implied by the time-series results in this paper could not have been profitably


employed.


It is important to realize that section is about the implementation of the coefficient


estimation procedure. It makes no statement on how much of these return predictabil

ity results will continue to exist in the future. Recent works explicitly making those


statements include Mclean and Pontiff (2016) and Hou et al. (2018).

# **9 Conclusion**


Contrary to prior beliefs, monthly stock market returns in the US can in fact be pre

dicted with past returns. Specifically, the U.S. stock market’s return during the first


month of a quarter correlates strongly with returns in future months, but the correla

tion is negative if the future month is the first month of a quarter, and positive if it


is not. I show that these first months of a quarter are ‘newsy’ because they contain


fresh earnings news, and argue that the return predictability pattern arises because


47


Electronic copy available at: https://ssrn.com/abstract=3480863


investors extrapolate these newsy month earnings to predict future earnings, but did


not recognize that earnings in future newsy months are inherently less predictable.


Survey data support this explanation, as does out-of-sample evidence across industries


and international markets. This paper seriously challenge the Efficient Market Hy

pothesis by documenting a strong and consistent form of return predictability. Behind


this return predictability result is a novel mechanism of expectation formation, which


features fundamentals extrapolation with a representative parameter.


48


Electronic copy available at: https://ssrn.com/abstract=3480863


# **References**

Abel, A. (1990). Asset Prices Under Habit Formation And Catching Up With The


Joneses. _American_ _Economic_ _Review_, 80:38–42.


Asness, C. S., Frazzini, A., and Pedersen, L. H. (2019). Quality minus junk. _Review_


_of_ _Accounting_ _Studies_, 24(1):34–112.


Asness, C. S., Moskowitz, T. J., and Pedersen, L. H. (2013). Value and Momentum


Everywhere. _The_ _Journal_ _of_ _Finance_, 68(3):929–985.


Ball, R. and Sadka, G. (2015). Aggregate earnings and why they matter. _Journal_ _of_


_Accounting_ _Literature_, 34:39–57.


Ball, R., Sadka, G., and Sadka, R. (2009). Aggregate Earnings and Asset Prices.


_Journal_ _of_ _Accounting_ _Research_, 47(5):1097–1133.


Bansal, R. and Yaron, A. (2004). Risks for the Long Run: A Potential Resolution of


Asset Pricing Puzzles. _The_ _Journal_ _of_ _Finance_, 59(4):1481–1509.


Barberis, N., Shleifer, A., and Vishny, R. (1998). A model of investor sentiment.


_Journal_ _of_ _Financial_ _Economics_, 49(3):307–343.


Barro, R. J. (2006). Rare Disasters and Asset Markets in the Twentieth Century*.


_The_ _Quarterly_ _Journal_ _of_ _Economics_, 121(3):823–866.


Beaver, W. H. (1968). The Information Content of Annual Earnings Announcements.


_Journal_ _of_ _Accounting_ _Research_, 6:67–92.


Bernard, V. L. and Thomas, J. K. (1989). Post-Earnings-Announcement Drift: Delayed


Price Response or Risk Premium? _Journal_ _of_ _Accounting_ _Research_, 27:1–36.


49


Electronic copy available at: https://ssrn.com/abstract=3480863


Bernard, V. L. and Thomas, J. K. (1990). Evidence that stock prices do not fully reflect


the implications of current earnings for future earnings. _Journal_ _of_ _Accounting_ _and_


_Economics_, 13(4):305–340.


Bordalo, P., Coffman, K., Gennaioli, N., Schwerter, F., and Shleifer, A. (2021a). Mem

ory and Representativeness.


Bordalo, P., Gennaioli, N., Kwon, S. Y., and Shleifer, A. (2021b). Diagnostic Bubbles.


_Journal_ _of_ _Financial_ _Economics_, 141(3).


Bordalo, P., Gennaioli, N., LaPorta, R., and Shleifer, A. (2019). Diagnostic Expecta

tions and Stock Returns. _Journal_ _of_ _Finance_, 74(6):2839–2874.


Bordalo, P., Gennaioli, N., Ma, Y., and Shleifer, A. (2020). Overreaction in Macroe

conomic Expectations.


Brochet, F., Kolev, K., and Lerman, A. (2018). Information transfer and conference


calls. _Review_ _of_ _Accounting_ _Studies_, 23(3):907–957.


Campbell, J. (2017). _Financial_ _Decisions_ _and_ _Markets:_ _A_ _Course_ _in_ _Asset_ _Pricing_ .


Princeton University Press.


Campbell, J. and Thompson, S. B. (2008). Predicting Excess Stock Returns Out of


Sample: Can Anything Beat the Historical Average? _Review_ _of_ _Financial_ _Studies_,


21(4):1509–1531.


Campbell, J. Y. and Cochrane, J. H. (1999). By Force of Habit: A Consumption-Based


Explanation of Aggregate Stock Market Behavior. _Journal_ _of_ _Political_ _Economy_,


107(2):205–251. Publisher: The University of Chicago Press.


Chambers, A. and Penman, S. (1984). Timeliness of Reporting and the Stock-Price


Reaction to Earnings Announcements. _Journal of Accounting Research_, 22(1):21–47.


50


Electronic copy available at: https://ssrn.com/abstract=3480863


Chang, T. Y., Hartzmark, S. M., Solomon, D. H., and Soltes, E. F. (2017). Being


Surprised by the Unsurprising: Earnings Seasonality and Stock Returns. _Review_ _of_


_Financial_ _Studies_, 30(1):281–323.


Chen, H., Dou, W., Guo, H., and Ji, Y. (2020a). Feedback and Contagion through


Distressed Competition. SSRN Scholarly Paper ID 3513296, Social Science Research


Network, Rochester, NY.


Chen, Y., Cohen, R. B., and Wang, Z. K. (2020b). Famous Firms, Earnings Clusters,


and the Stock Market. SSRN Scholarly Paper ID 3685452, Social Science Research


Network, Rochester, NY.


Clinch, G. J. and Sinclair, N. A. (1987). Intra-industry information releases: A recursive


systems approach. _Journal_ _of_ _Accounting_ _and_ _Economics_, 9(1):89–106.


Constantinides, G. M. (1990). Habit Formation: A Resolution of the Equity Premium


Puzzle. _Journal_ _of_ _Political_ _Economy_, 98(3):519–543.


deHaan, E., Shevlin, T., and Thornock, J. (2015). Market (in)attention and the strate

gic scheduling and timing of earnings announcements. _Journal_ _of_ _Accounting_ _and_


_Economics_, 60(1):36–55.


Dellavigna, S. and Pollet, J. M. (2009). Investor Inattention and Friday Earnings


Announcements. _The_ _Journal_ _of_ _Finance_, 64(2):709–749.


Enke, B. and Zimmermann, F. (2017). Correlation Neglect in Belief Formation. _The_


_Review_ _of_ _Economic_ _Studies_ .


Fama, E. (1998). Market efficiency, long-term returns, and behavioral finance. _Journal_


_of_ _Financial_ _Economics_, 49(3):283–306.


Fama, E. F. (1965). The Behavior of Stock-Market Prices. _The_ _Journal_ _of_ _Business_,


38(1):34–105.


51


Electronic copy available at: https://ssrn.com/abstract=3480863


Fama, E. F. (1970). Efficient Capital Markets: A Review of Theory and Empirical


Work. _The_ _Journal_ _of_ _Finance_, 25(2):383–417.


Fama, E. F. and MacBeth, J. D. (1973). Risk, Return, and Equilibrium: Empirical


Tests. _Journal of Political Economy_, 81(3):607–636. Publisher: University of Chicago


Press.


Fedyk, A. and Hodson, J. (2019). When Can the Market Identify Old News? SSRN


Scholarly Paper ID 2433234, Social Science Research Network, Rochester, NY.


Foster, G. (1981). Intra-industry information transfers associated with earnings re

leases. _Journal_ _of_ _Accounting_ _and_ _Economics_, 3(3):201–232.


Gabaix (2012). Variable Rare Disasters: An Exactly Solved Framework for Ten Puzzles


in Macro-Finance. _Quarterly_ _Journal_ _of_ _Economics_, 127(2):645–700.


Garg, A., Goulding, C. L., Harvey, C. R., and Mazzoleni, M. (2021). Momentum


Turning Points. SSRN Scholarly Paper ID 3489539, Social Science Research Network,


Rochester, NY.


Givoly, D. and Palmon, D. (1982). Timeliness of Annual Earnings Announcements:


Some Empirical Evidence. _The_ _Accounting_ _Review_, 57(3):486–508.


Goyal, A. and Welch, I. (2008). A Comprehensive Look at The Empirical Performance


of Equity Premium Prediction. _The_ _Review_ _of_ _Financial_ _Studies_, 21(4):1455–1508.


Greenwood, R. and Hanson, S. G. (2013). Issuer Quality and Corporate Bond Returns.


_The_ _Review_ _of_ _Financial_ _Studies_, 26(6):1483–1525.


Guo, H. and Wachter, J. A. (2019). ’Superstitious’ Investors. SSRN Scholarly Paper


ID 3245298, Social Science Research Network, Rochester, NY.


52


Electronic copy available at: https://ssrn.com/abstract=3480863


Han, J. C. Y. and Wild, J. J. (1990). Unexpected Earnings and Intraindustry Informa

tion Transfers: Further Evidence. _Journal_ _of_ _Accounting_ _Research_, 28(1):211–219.


Han, J. C. Y., Wild, J. J., and Ramesh, K. (1989). Managers’ earnings forecasts and


intra-industry information transfers. _Journal of Accounting and Economics_, 11(1):3–


33.


Hann, R. N., Kim, H., and Zheng, Y. (2019). Intra-Industry Information Transfers: Ev

idence from Changes in Implied Volatility around Earnings Announcements. SSRN


Scholarly Paper ID 3173754, Social Science Research Network, Rochester, NY.


Hann, R. N., Li, C., and Ogneva, M. (2020). Another Look at the Macroeconomic


Information Content of Aggregate Earnings: Evidence from the Labor Market. _The_


_Accounting_ _Review_, 96(2):365–390.


Hartzmark, S. M. and Shue, K. (2018). A Tough Act to Follow: Contrast Effects in


Financial Markets. _The_ _Journal_ _of_ _Finance_, 73(4):1567–1613.


Hartzmark, S. M. and Solomon, D. H. (2013). The dividend month premium. _Journal_


_of_ _Financial_ _Economics_, 109(3):640–660.


Heston, S. L. and Sadka, R. (2008). Seasonality in the cross-section of stock returns.


_Journal_ _of_ _Financial_ _Economics_, 87(2):418–445.


Hou, K., Xue, C., and Zhang, L. (2018). Replicating Anomalies. _The_ _Review_ _of_


_Financial_ _Studies_ .


Jegadeesh, N. and Titman, S. (1993). Returns to Buying Winners and Selling Losers:


Implications for Stock Market Efficiency. _The_ _Journal_ _of_ _Finance_, 48(1):65–91.


Jensen, T. I., Kelly, B. T., and Pedersen, L. H. (2021). Is There a Replication Crisis


in Finance? SSRN Scholarly Paper ID 3774514, Social Science Research Network,


Rochester, NY.


53


Electronic copy available at: https://ssrn.com/abstract=3480863


Johnson, T. L., Kim, J., and So, E. C. (2020). Expectations Management and Stock


Returns. _The_ _Review_ _of_ _Financial_ _Studies_, 33(10):4580–4626.


Johnson, T. L. and So, E. C. (2018a). Asymmetric Trading Costs Prior to Earnings An

nouncements: Implications for Price Discovery and Returns. _Journal_ _of_ _Accounting_


_Research_, 56(1):217–263.


Johnson, T. L. and So, E. C. (2018b). Time Will Tell: Information in the Tim

ing of Scheduled Earnings News. _Journal_ _of_ _Financial_ _and_ _Quantitative_ _Analysis_,


53(6):2431–2464.


Keloharju, M., Linnainmaa, J. T., and Nyberg, P. (2016). Return Seasonalities. _The_


_Journal_ _of_ _Finance_, 71(4):1557–1590.


Kendall, M. G. and Hill, A. B. (1953). The Analysis of Economic Time-Series-Part I:


Prices. _Journal_ _of_ _the_ _Royal_ _Statistical_ _Society._ _Series_ _A_ _(General)_, 116(1):11–34.


Kraft, A. G., Vashishtha, R., and Venkatachalam, M. (2017). Frequent Financial


Reporting and Managerial Myopia. _The_ _Accounting_ _Review_, 93(2):249–275.


Kross, W. (1981). Earnings and announcement time lags. _Journal of Business Research_,


9(3):267–281.


Kross, W. and Schroeder, D. A. (1984). An Empirical Investigation of the Effect of


Quarterly Earnings Announcement Timing on Stock Returns. _Journal of Accounting_


_Research_, 22(1):153–176.


Lakonishok, J., Shleifer, A., and Vishny, R. W. (1994). Contrarian Investment, Ex

trapolation, and Risk. _The_ _Journal_ _of_ _Finance_, 49(5):1541–1578.


Matthies, B. (2018). Biases in the Perception of Covariance. SSRN Scholarly Paper


ID 3223227, Social Science Research Network, Rochester, NY.


54


Electronic copy available at: https://ssrn.com/abstract=3480863


Mclean, R. D. and Pontiff, J. (2016). Does Academic Research Destroy Stock Return


Predictability? _The_ _Journal_ _of_ _Finance_, 71(1):5–32.


Mehra, R. and Prescott, E. C. (1985). The equity premium: A puzzle. _Journal_ _of_


_Monetary_ _Economics_, 15(2):145–161.


Moskowitz, T. J. and Grinblatt, M. (1999). Do Industries Explain Momentum? _The_


_Journal_ _of_ _Finance_, 54(4):1249–1290.


Moskowitz, T. J., Ooi, Y. H., and Pedersen, L. H. (2012). Time series momentum.


_Journal_ _of_ _Financial_ _Economics_, 104(2):228–250.


Nagel, S. and Xu, Z. (2019). Asset Pricing with Fading Memory. Working Paper 26255,


National Bureau of Economic Research. Series: Working Paper Series.


Noh, S., So, E. C., and Verdi, R. S. (2021). Calendar rotations: A new approach for


studying the impact of timing using earnings announcements. _Journal_ _of_ _Financial_


_Economics_, 140(3):865–893.


Patatoukas, P. N. (2014). Detecting news in aggregate accounting earnings: implica

tions for stock market valuation. _Review_ _of_ _Accounting_ _Studies_, 19(1):134–160.


Payne, J. L. and Thomas, W. B. (2003). The Implications of Using Stock-Split Adjusted


I/B/E/S Data in Empirical Research. _The_ _Accounting_ _Review_, 78(4):1049–1067.


Poterba, J. M. and Summers, L. H. (1988). Mean reversion in stock prices: Evidence


and Implications. _Journal_ _of_ _Financial_ _Economics_, 22(1):27–59.


Ramnath, S. (2002). Investor and Analyst Reactions to Earnings Announcements of


Related Firms: An Empirical Analysis. _Journal of Accounting Research_, 40(5):1351–


1376.


55


Electronic copy available at: https://ssrn.com/abstract=3480863


Rietz, T. A. (1988). The equity risk premium a solution. _Journal_ _of_ _Monetary_ _Eco-_


_nomics_, 22(1):117–131.


Savor, P. and Wilson, M. (2016). Earnings Announcements and Systematic Risk. _The_


_Journal_ _of_ _Finance_, 71(1):83–138.


Thomas, J. and Zhang, F. (2008). Overreaction to Intra-industry Information Trans

fers? _Journal_ _of_ _Accounting_ _Research_, 46(4):909–940.


Vuolteenaho, T. (2002). What Drives Firm-Level Stock Returns? _The_ _Journal_ _of_


_Finance_, 57(1):233–264.


Wachter, J. A. (2013). Can Time-Varying Risk of Rare Disasters Explain Aggregate


Stock Market Volatility? _The_ _Journal_ _of_ _Finance_, 68(3):987–1035.


Wang, C. (2020). Under- and Over-Reaction in Yield Curve Expectations. SSRN


Scholarly Paper ID 3487602, Social Science Research Network, Rochester, NY.


56


Electronic copy available at: https://ssrn.com/abstract=3480863


**Table** **1**


**Company-fiscal** **period** **count** **by** **fiscal** **period** **end** **month**


US Global


Count Percent Count Percent


Group 1: Jan/Apr/Jul/Oct 78,747 8.85 56,951 5.74


Group 2: Feb/May/Aug/Nov 49,385 5.55 64,303 6.49


Group 3: Mar/Jun/Sep/Dec 761,310 85.59 870,263 87.77


Total 889,442 100.00 991,517 100.00


The table tabulates the number of company-quarter by 3 groups, where the groups are determined by the fiscal quarter
end month, specifically its remainder when divided by 3. First two columns contain count and percentage on the full
sample of US companies. The next two columns do the same tabulation on the full sample of global companies. For the
US sample, data are quarterly from 1971 to 2021. For the global sample, data are quarterly and semi-annually from 1998
to 2021.


**Table** **2**


**US** **company-quarter** **count** **by** **reporting** **month**


Both filters Rpt Lag _<_ = 92 Group 3 FQ end No filter


Count Pct Count Pct Count Pct Count Pct


Group 1: Jan/Apr/Jul/Oct 345,986 46.47 375,787 43.24 357,265 46.93 387,466 43.56


Group 2: Feb/May/Aug/Nov 344,666 46.30 380,792 43.81 348,118 45.73 385,806 43.38


Group 3: Mar/Jun/Sep/Dec 53,830 7.23 112,594 12.95 55,927 7.35 116,170 13.06


Total 744,482 100.00 869,173 100.00 761,310 100.00 889,442 100.00


The table tabulates the number of company-quarter by 3 groups, where the groups are determined by the reporting month,
specifically its remainder when divided by 3. If a company reports earnings for a given fiscal quarter in October, this
company-quarter belongs to group 1, as 10 _≡_ 1 mod 3. First two columns contain count and percentage on the sample
where 1) reporting within 92 days and 2) aligned with calendar quarters. The next two columns do the same tabulation
with only the first filter. The next two columns apply only the second filter. The last two columns apply no filter. Data
are quarterly from 1971 to 2021.


**Table** **3**


**Lead-lag** **relations** **of** **US** **monthly** **market** **returns**


(1) (2) (3) (4)


All NM Non-NM Difference


_mktnm_ ( _t,_ 1) 0.090* -0.168** 0.219*** -0.388***


[1.73] [-2.32] [3.92] [-4.23]


_mktnm_ ( _t,_ 2) 0.014 -0.177*** 0.109** -0.287***


[0.34] [-2.85] [2.29] [-3.66]


_mktnm_ ( _t,_ 3) 0.069 0.041 0.083** -0.042


[1.55] [0.44] [2.07] [-0.41]


_mktnm_ ( _t,_ 4) 0.027 -0.086 0.084** -0.169**


[0.69] [-1.26] [2.09] [-2.14]


_const_ 0.007*** 0.017*** 0.002 0.015***


[3.40] [4.77] [0.86] [3.53]


N 1,136 378 758 1,136


R-sq 0.013 0.064 0.072 0.070


Column 1 of this table reports results from the following monthly time-series regression:
_mktt_ = _α_ + [�] _j_ [4] =1 _[β][j][mkt][nm]_ [(] _[t,j]_ [)][ +] _[ ϵ][t]_ [.] [Here] _[mkt][t]_ [is] [the] [US] [aggregate] [market] [return] [in]
month _t_, and _mktnm_ ( _t,j_ ) is the return in the _j_ th newsy month (Jan, Apr, Jul, Oct)
preceding month _t_ . Column 2 reports the same regression on the subsample where the
dependent variable is returns of the newsy months. Column 3 is for the non-newsy
months. Column 4 reports the difference between the coefficients in column 2 and 3,
extracted from this regression _mktt_ = _α_ + [�] _j_ [4] =1 _[β][j][mkt][nm]_ [(] _[t,j]_ [)] [+][ �][4] _j_ =1 _[γ][j][mkt][nm]_ [(] _[t,j]_ [)] _[×]_
_It_ _[nm]_ + _δIt_ _[nm]_ + _ϵt_, where _It_ _[nm]_ is a dummy variable taking the value of 1 when month
_t_ is newsy. Data are monthly from 1926 to 2021. T-statistics computed with White
standard errors are reported in square brackets.


59


Electronic copy available at: https://ssrn.com/abstract=3480863


**Table** **4**


**Lead-lag** **relations** **of** **US** **monthly** **market** **returns,** **across** **subsamples**


(1) (2) (3) (4) (5) (6) (7)


All NM Non-NM All Post-WW2 First Half Second Half
�4 _j_ =1 _[mkt][nm]_ [(] _[t,j]_ [)] 0.052** -0.103*** 0.129*** 0.129*** 0.082*** 0.162*** 0.090***

[2.04] [-2.67] [4.76] [4.76] [3.59] [3.86] [3.17]
�4 _j_ =1 _[mkt][nm]_ [(] _[t,j]_ [)] _[ ×][ I]_ _t_ _[nm]_ -0.232*** -0.157*** -0.279*** -0.176***

[-4.93] [-3.51] [-3.96] [-3.09]

_It_ _[nm]_ 0.016*** 0.011*** 0.019*** 0.012**

[3.51] [2.68] [2.68] [2.26]


_const_ 0.007*** 0.017*** 0.002 0.002 0.005** -0.001 0.005


[3.30] [4.60] [0.74] [0.74] [2.16] [-0.19] [1.56]


N 1,136 378 758 1,136 893 567 569


R-sq 0.008 0.029 0.057 0.047 0.026 0.061 0.032


Column 1 of this table reports results from the following monthly time-series regression: _mktt_ = _α_ + _β_ [�] _j_ [4] =1 _[mkt][nm]_ [(] _[t,j]_ [)] [+] _[ϵ][t]_ [.]
Here _mktt_ is the US aggregate market return in month _t_, and _mktnm_ ( _t,j_ ) is the return in the _j_ th newsy month (Jan, Apr,
Jul, Oct) preceding month _t_ . Column 2 reports the same regression as in 1, but on the subsample where the dependent
variable is returns of the newsy months. Column 3 is for the non-newsy months. Column 4 reports the results of
_mktt_ = _α_ + _β_ 1 �4 _j_ =1 _[mkt][nm]_ [(] _[t,j]_ [)] [+] _[ β]_ [2][(][�][4] _j_ =1 _[mkt][nm]_ [(] _[t,j]_ [)][)] _[ ×][ I]_ _t_ _[nm]_ + _β_ 3 _It_ _[nm]_ + _ϵt_, where _It_ _[nm]_ is a dummy variable taking the
value of 1 when month _t_ is newsy. Column 5-7 report results for the regression in column 4 on the subsamples of the
post-WW2 period (1947-2021), the first half (1926-1973), and the second half (1974-2021). T-statistics computed with
White standard errors are reported in square brackets.


**Table** **5**


**Lead-lag** **relations** **of** **US** **monthly** **market** **returns,** **actual** **vs** **simulated** **data**


Actual Simulated


(1) (2) (3) (4) (5) (6)
�4 _j_ =1 _[mkt][nm]_ [(] _[t,j]_ [)] 0.129*** 0.128*** 0.015 0.014

[4.76] [4.43] [0.75] [0.71]
�4 _j_ =1 _[mkt][nm]_ [(] _[t,j]_ [)] _[×][ I]_ _t_ _[nm]_ -0.232*** -0.216*** -0.019 -0.023

[-4.93] [-5.01] [-0.62] [-0.69]
�12 _j_ =1 _[mkt][t][−][j]_ 0.042** 0.007

[2.39] [0.71]
�12 _j_ =1 _[mkt][t][−][j]_ _[×][ I]_ _t_ _[nm]_ -0.090*** 0.000

[-2.77] [-0.01]
�8 _j_ =1 _[mkt][nnm]_ [(] _[t,j]_ [)] 0.004 0.003

[0.15] [0.21]
�8 _j_ =1 _[mkt][nnm]_ [(] _[t,j]_ [)] _[×][ I]_ _t_ _[nm]_ -0.031 0.011

[-0.69] [0.51]


N 1,136 1,134 1,134 1,136 1,134 1,134


R-sq 0.047 0.028 0.049 0.003 0.003 0.006


Column 1-3 are on actual data. Column 4-6 perform the same set of regressions on simulated
data. Column 1 of this table reports results from the following monthly time-series regression:
_mktt_ = _α_ + _β_ 1 �4 _j_ =1 _[mkt][nm]_ [(] _[t,j]_ [)] [+] _[ β]_ [2][(][�][4] _j_ =1 _[mkt][nm]_ [(] _[t,j]_ [)][)] _[ ×][ I]_ _t_ _[nm]_ + _β_ 3 _It_ _[nm]_ + _ϵt_ . Here _mktt_ is the
US aggregate market return in month _t_, _mktnm_ ( _t,j_ ) is the return in the _j_ th newsy month
(Jan, Apr, Jul, Oct) preceding the month _t_, and _It_ _[nm]_ is a dummy variable taking the value
of 1 when month _t_ is newsy. Column 2 reports results of the following regression: _mktt_ =
_α_ + _β_ 1 �12 _j_ =1 _[mkt][t][−][j]_ [+] _[ β]_ [2][(][�][12] _j_ =1 _[mkt][t][−][j]_ [)] _[ ×][ I]_ _t_ _[nm]_ + _β_ 3 _It_ _[nm]_ + _ϵt_ . Here _mktt−j_ is the aggregate
market returns _j_ calendar months before month _t_ . Column 3 is the regression in column 1
with two additional independent variables [�] _j_ [8] =1 _[mkt][nnm]_ [(] _[t,j]_ [)] [and] [(][�][8] _j_ =1 _[mkt][nnm]_ [(] _[t,j]_ [)][)] _[ ×][ I]_ _t_ _[nm]_ .
Here, _mktnnm_ ( _t,j_ ) is the US aggregate market return in the _j_ th non-newsy month preceding
the month _t_ . Data are monthly from 1926 to 2021. Column 4-6 report results from the same
regressions as in column 1-3 respectively, except here they are done on simulated AR(1) times
series with the first order autocorrelation of 0.11. The regression coefficients in column 4-6
are average of the 10,000 coefficients each computed from a separate simulation. For column
1-3, t-statistics computed with White standard errors are reported in square brackets. For
column 4-6, standard errors are standard deviations of coefficients across simulations, and
the corresponding t-statistics are reported in square brackets.


61


Electronic copy available at: https://ssrn.com/abstract=3480863


**Table** **6**


**Lead-lag** **relations** **of** **US** **monthly** **earnings**


(1) (2) (3) (4)


All NM Non-NM Difference


Panel A: Report Lag _≤_ 92 & Group 3 Month FQ end
�12 _j_ =1 _[roe][t][−][j]_ 0.051*** 0.027*** 0.064*** -0.036***

[5.30] [3.96] [5.81] [-3.57]


N 587 196 391 587


Panel B: Report Lag _≤_ 92
�12 _j_ =1 _[roe][t][−][j]_ 0.060*** 0.041*** 0.070*** -0.029***

[5.32] [4.56] [5.97] [-3.31]


N 587 196 391 587


Panel C: Group 3 Month FQ end
�12 _j_ =1 _[roe][t][−][j]_ 0.053*** 0.025*** 0.067*** -0.043***

[5.58] [3.71] [6.46] [-4.17]


N 587 196 391 587


Panel D: No filter
�12 _j_ =1 _[roe][t][−][j]_ 0.060*** 0.040*** 0.071*** -0.032***

[5.24] [4.63] [5.76] [-3.32]


N 587 196 391 587


Column 1 of this table reports results from the following monthly time-series regressions:
_roet_ = _α_ + _β_ [�] _j_ [12] =1 _[roe][t][−][j]_ [+] _[ ϵ][t]_ [.] [Here] _[roe][t]_ [is] [the] [aggregate] [roe,] [or] [the] [aggregate] [net] [income]
before extraordinary items divided by aggregate book value of equity, of firms announcing
their earnings in month _t_ . Column 2 and 3 report results from the same regression except
on the subsample where the dependent variables are newsy and non-newsy month returns,
respectively. Column 4 reports the difference between column 2 and 3. Panel A aggregates
ROE only on firm-quarters that are 1) reporting within 92 days and 2) aligned with calendar
quarters. Panel B applies only the first filter; panel C only the second; panel D none. Data
are monthly from 1971 to 2021. T-statistics computed with Newey-West standard errors are
reported in square brackets.


62


Electronic copy available at: https://ssrn.com/abstract=3480863


**Table** **7**


**No** **reversal** **in** **the** **pre-season** **portion** **of** **the** **newsy** **months**


US Global


(1) (2) (3) (4) (5) (6)

_mktt_ _mkt_ _[FW]_ _t_ _mkt_ _[ExclFW]_ _t_ _mktc,t_ _mkt_ _[PS]_ _c,t_ _mkt_ _[ExclPS]_ _c,t_
�4 _j_ =1 _[mkt][nm]_ [(] _[t,j]_ [)] -0.103*** 0.019 -0.120*** -0.029 0.011 -0.040**

[-2.67] [1.03] [-2.92] [-1.07] [0.76] [-2.29]


_const_ 0.017*** 0.005*** 0.012*** 0.017*** 0.008*** 0.009***


[4.60] [3.35] [3.38] [3.21] [2.66] [2.72]


N 378 378 378 2,305 2,305 2,305


R-sq 0.029 0.005 0.047 0.006 0.002 0.022


Column 1 of this table reports results from the following monthly time-series regression: _mktt_ = _α_ + _β_ [�] _j_ [4] =1 _[mkt][nm]_ [(] _[t,j]_ [)] [+] _[ϵ][t]_ [,]
on the subsample where the dependent variable is the first month of a quarter, or Jan, Apr, Jul, Oct. Here _mktt_ the
market return in month _t_, and _mktnm_ ( _t,j_ ) is the market return in the _j_ th newsy month preceding month _t_ . Column 2
replaces the dependent variable with _mkt_ _[FW]_ _t_, which is the aggregate market return in the first five trading days in month
_t_ . Column 3 has the dependent variable _mkt_ _[ExclFW]_ _t_, which is the aggregate market return in month _t_ excluding the first
five trading days. Column 4 does the regression _mktc,t_ = _α_ + _β_ [�] _j_ [4] =1 _[mkt][c,nm]_ [(] _[t,j]_ [)][ +] _[ ϵ][c,t]_ [,] [again] [on] [cases] [where] [month] _[t]_ [are]
the first months of the quarters. Here _mktc,t_ is the aggregate market return in month _t_ for country _c_, and _mktc,nm_ ( _t,j_ ) is
the aggregate market return in the _j_ th newsy “month” (Jan+Feb, Apr+May, Jul+Aug, Oct+Nov) preceding the month _t_
for country _c_ . Column 5 replaces the dependent variable with _mkt_ _[PS]_ _c,t_ [, the pre-earnings season returns.] [They are returns in]
the first 5, 10, or 15 trading day of the month, depending on country _c_ ’s reporting speed. Column 6 changes the dependent
variable to _mkt_ _[ExclPS]_ _c,t_, which equals _mktc,t −_ _mkt_ _[PS]_ _c,t_ [.] [For] [the] [US] [sample,] [data] [are] [monthly] [from] [1926] [to] [2021.] [For] [the]
global sample, data are monthly from 1964 to 2021. This shorter sample is due to the availability of the daily return
data. T-statistics computed with White standard errors are reported in square brackets for column 1-3. Columns 4-6 use
standard errors clustered at the monthly level.


**Table** **8**


**Weak** **dynamic** **autocorrelation** **in** **Q1**


Q2, Q3, and Q4 Q1


(1) (2) (3) (4) (5) (6)


Group 1 Group 2 Group 3 Jan Feb Mar
�4 _j_ =1 _[mkt][nm]_ [(] _[t,j]_ [)] -0.125*** 0.173*** 0.121*** -0.024 0.056 0.084

[-2.83] [3.67] [2.95] [-0.35] [1.07] [1.14]


_const_ 0.017*** 0.003 0.000 0.016*** 0.003 0.002


[3.79] [0.69] [0.10] [2.88] [0.58] [0.33]


N 283 284 284 95 95 95


R-sq 0.040 0.088 0.054 0.002 0.015 0.023


This table reports results from the following monthly time-series regression: _mktt_ = _α_ + _β_ [�] _j_ [4] =1 _[mkt][nm]_ [(] _[t,j]_ [)][ +] _[ϵ][t]_ [.] [Here] _[ mkt][t]_
is the US aggregate market return in month _t_, and _mktnm_ ( _t,j_ ) is the return in the _j_ th newsy month (Jan, Apr, Jul, Oct)
preceding month _t_ . Column 1-3 are where the dependent variables are group 1-3 months outside the first quarter. Column
4-6 are where the dependent variables are returns of January, February, and March. Data are monthly from 1926 to 2021.
T-statistics computed with White standard errors are reported in square brackets.


**Table** **9**


**Survey** **evidence** **from** **IBES**


(1) (2) (3) (4) (5)


All NM Non-NM All All
�12 _j_ =1 _[Sup][t][−][j]_ 0.061*** 0.049*** 0.068*** 0.068***

[8.54] [4.82] [9.96] [9.95]
�12 _j_ =1 _[Sup][t][−][j]_ _[×][ I]_ _t_ _[nm]_ -0.019**

[-2.18]
�4 _j_ =1 _[Sup][nm]_ [(] _[t,j]_ [)] 0.584***

[3.12]
�4 _j_ =1 _[Sup][nm]_ [(] _[t,j]_ [)] _[ ×][ I]_ _t_ _[nm]_ -0.064**

[-2.26]

_It_ _[nm]_ 0.001*** 0.001***

[7.71] [6.12]


_const_ -0.000 0.000*** -0.000*** -0.000*** -0.001***


[-1.08] [3.62] [-3.90] [-3.87] [-5.91]


N 419 140 279 419 419


Column 1 of this table reports results from the following monthly time-series regression: _Supt_ = _α_ + _β_ [�] _j_ [12] =1 _[Sup][t][−][j]_ [+] _[ ϵ][t]_ [.]
Here _Supt_ is the aggregate earnings surprise in month _t_, which is market cap weighted average of firm level earnings
surprises of all firms announcing in month _t_ . The firm level earnings surprises are computed as the difference between
realized EPS and expected EPS divided by the firm’s stock price at the end of the previous month. Column 2 reports
the same regression as in 1, but on the subsample where the dependent variable is aggregate surprises of the newsy
months. Column 3 is for the non-newsy months. Column 4 reports the difference between the coefficients in column 2
and 3, extracted from a regression with additional interaction terms to _It_ _[nm]_, which is a dummy variable taking value 1
if month _t_ is newsy. Column 5 performs the same regression as in column 4, except additionally confine the surprises
on the right-hand-side to be those in newsy months. Data are monthly from 1985 to 2021. T-statistics computed with
Newey-West standard errors are reported in square brackets.


**Table** **10**


**Lead-lag** **relations** **of** **monthly** **excess** **industry** **returns** **in** **the** **US**


(1) (2) (3) (4)


All NM Non-NM Difference


_exreti,nm_ ( _t,_ 1) 0.023 -0.036 0.052** -0.087**


[1.23] [-1.40] [2.14] [-2.49]


_exreti,nm_ ( _t,_ 2) -0.004 -0.024 0.005 -0.029


[-0.28] [-0.90] [0.29] [-0.90]


_exreti,nm_ ( _t,_ 3) 0.024 -0.012 0.042** -0.054


[1.47] [-0.42] [2.17] [-1.56]


_exreti,nm_ ( _t,_ 4) 0.036** 0.004 0.052** -0.048


[2.21] [0.15] [2.48] [-1.51]


_const_ -0.001 0.001 -0.001*** 0.002***


[-1.48] [1.44] [-3.10] [2.83]


N 19,108 6,353 12,755 19,108


R-sq 0.003 0.002 0.009 0.006


Column 1 of this table reports results from the following industry-month level panel
regression: _exreti,t_ = _α_ + [�][4] _j_ =1 _[β][j][exret][i,nm]_ [(] _[t,j]_ [)][ +] _[ϵ][i,t]_ [.] [Here] _[ exret][i,t]_ [is the value weighted]
average return of industry _i_ in excess of the market in month _t_, and _exreti,nm_ ( _t,j_ ) is
the excess return in the _j_ th newsy month (Jan, Apr, Jul, Oct) preceding month _t_ .
The industry is defined by the firm’s 4-digit SIC code. Column 2 reports the same
regression on the subsample where the dependent variable is returns of the newsy
months. Column 3 is for the non-newsy months. Column 4 reports the difference
between the coefficients in column 2 and 3, extracted from this regression _exreti,t_ =
_α_ + [�][4] _j_ =1 _[β][j][exret][i,nm]_ [(] _[t,j]_ [)][+][�] _j_ [4] =1 _[γ][j][exret][i,nm]_ [(] _[t,j]_ [)] _[×][I]_ _t_ _[nm]_ + _δIt_ _[nm]_ + _ϵi,t_, where _It_ _[nm]_ is a dummy
variable taking the value of 1 when month _t_ is newsy. Regressions are weighted by the
market cap of industry _i_ as of the month _t −_ 1, normalized by the total market cap
in the cross section. 20 stocks are required in each month-industry. Data are monthly
from 1926 to 2021. T-statistics computed with clustered standard errors by month are
reported in square brackets.


66


Electronic copy available at: https://ssrn.com/abstract=3480863


**Table** **11**


**Lead-lag** **relations** **of** **monthly** **excess** **industry** **returns** **in** **US,** **by** **different**
**industry** **measures**


(1) (2) (3) (4)


All NM Non-NM Difference


Panel A: SIC Major Group
�4 _j_ =1 _[exret][i,nm]_ [(] _[t,j]_ [)] 0.021*** -0.012 0.038*** -0.050***

[2.89] [-0.96] [4.35] [-3.26]


N 28,028 9,327 18,701 28,028


R-sq 0.002 0.001 0.007 0.004


Panel B: SIC Industry Group
�4 _j_ =1 _[exret][i,nm]_ [(] _[t,j]_ [)] 0.020*** -0.008 0.034*** -0.041***

[2.76] [-0.64] [3.81] [-2.78]


N 24,082 8,037 16,045 24,082


R-sq 0.002 0.000 0.005 0.004


Panel C: SIC Industry
�4 _j_ =1 _[exret][i,nm]_ [(] _[t,j]_ [)] 0.020** -0.017 0.038*** -0.055***

[2.51] [-1.39] [3.84] [-3.50]


N 19,108 6,353 12,755 19,108


R-sq 0.002 0.001 0.007 0.005


Column 1 of this table reports results from the following industry-month level panel regression: _exreti,t_ = _α_ + _β_ [�] _j_ [4] =1 _[exret][i,nm]_ [(] _[t,j]_ [)] [+] _[ϵ][i,t]_ [.] Here _exreti,t_ is the value weighted
average return of industry _i_ in excess of the market in month _t_, and _exreti,nm_ ( _t,j_ ) is the
excess return in the _j_ th newsy month (Jan, Apr, Jul, Oct) preceding month _t_ . Column 2 reports the same regression on the subsample where the dependent variable are
returns of the newsy months. Column 3 is for the non-newsy months. Column 4 reports
the difference between the coefficients in column 2 and 3, extracted from this regression
_exreti,t_ = _α_ + _β_ [�] _j_ [4] =1 _[exret][i,nm]_ [(] _[t,j]_ [)] [+] _[γ]_ [ �][4] _j_ =1 _[exret][i,nm]_ [(] _[t,j]_ [)] _[×]_ _[I]_ _t_ _[nm]_ + _δIt_ _[nm]_ + _ϵi,t_, where _It_ _[nm]_ is a
dummy variable taking the value of 1 when month _t_ is newsy. Panel A to C differ only in the
industry variable used. Regressions are weighted by the market cap of industry _i_ as of the
month _t −_ 1, normalized by the total market cap of each cross section. 20 stocks are required
in each month-industry. Data are monthly from 1926 to 2021. T-statistics computed with
clustered standard errors by month are reported in square brackets.


67


Electronic copy available at: https://ssrn.com/abstract=3480863


**Table** **12**


**Lead-lag** **relations** **of** **monthly** **excess** **industry** **earnings** **in** **US**


(1) (2) (3) (4)


All NM Non-NM Difference


Panel A: Report Lag _≤_ 92 & Group 3 Month FQ end
�12 _j_ =1 _[exroe][i,t][−][j]_ 0.027*** 0.016*** 0.054*** -0.037***

[7.03] [4.51] [10.57] [-6.96]


N 18,462 6,958 11,504 18,462


R-sq 0.090 0.060 0.169 0.125


Panel B: Report Lag _≤_ 92
�12 _j_ =1 _[exroe][i,t][−][j]_ 0.044*** 0.033*** 0.064*** -0.031***

[11.53] [6.81] [13.82] [-4.75]


N 24,835 8,683 16,152 24,835


R-sq 0.148 0.125 0.194 0.165


Panel C: Group 3 Month FQ end
�12 _j_ =1 _[exroe][i,t][−][j]_ 0.027*** 0.017*** 0.053*** -0.036***

[7.13] [4.87] [10.18] [-6.82]


N 19,206 7,215 11,991 19,206


R-sq 0.096 0.068 0.171 0.129


Panel D: No filter
�12 _j_ =1 _[exroe][i,t][−][j]_ 0.043*** 0.033*** 0.061*** -0.029***

[11.26] [7.00] [12.73] [-4.50]


N 25,812 9,015 16,797 25,812


R-sq 0.148 0.129 0.188 0.163


Column 1 of this table reports results from the following industry-month level panel regression: _exroei,t_ = _α_ + _β_ [�] _j_ [12] =1 _[exroe][i,t][−][j]_ [+] _[ ϵ][t]_ [.] [Here] _[exroe][i,t]_ [=] _[roe][i,t][ −]_ _[roe][t]_ [,] [where] _[roe][i,t]_ [is] [the]
roe aggregated for industry _i_ among all of its announcers in month _t_, or the aggregate net
income before extraordinary items divided by aggregate book value of equity, and _roet_ is
the aggregate roe on all firms announcing in month _t_ . The ROE is then winsorized at the
10th and the 90th percentiles of each cross section to limit the impact of extreme data. It is
filled with a neutral value of zero when missing as part of the independent variable, but kept
missing when used individually as the dependent variable. Column 2 and 3 report results
from the same regression except on the subsample where the dependent variables are newsy
and non-newsy month returns, respectively. Column 4 reports the difference between column
2 and 3. Panel A aggregates ROE only on firm-quarters that are 1) reporting within 92 days
and 2) aligned with calendar quarters. Panel B applies only the first filter; panel C only the
second; panel D none. The regressions are weighted by aggregate book value of equity of the
industry-month divided by the total book value of the year. 20 stocks are required for each

68

industry-quarter. Data are monthly from 1971 to 2021. T-statistics computed with standard
errors double clustered at the month, industry level are reported in square brackets.


Electronic copy available at: https://ssrn.com/abstract=3480863


**Table** **13**


**Heterogeneous** **effect** **across** **industries**


(1) (2) (3) (4) (5) (6) (7) (8)


connectivity entry cost balance size


low high low high low high small large
�4 _j_ =1 _[exret][i,nm]_ [(] _[t,j]_ [)] 0.041** 0.057*** 0.047** 0.058*** 0.043* 0.063*** 0.018*** 0.030***

[2.35] [2.85] [2.02] [3.00] [1.95] [3.40] [3.30] [4.57]
�4 _j_ =1 _[exret][i,nm]_ [(] _[t,j]_ [)] _[ ×][ I]_ _t_ _[nm]_ -0.039 -0.134*** -0.040 -0.115*** -0.041 -0.123*** -0.016 -0.031***

[-1.28] [-4.03] [-1.05] [-3.31] [-1.00] [-3.81] [-1.61] [-2.84]


N 7,571 7,290 5,376 4,899 4,830 5,390 250,034 183,316


R-sq 0.004 0.013 0.005 0.011 0.004 0.013 0.002 0.002


This table reports results on the following industry-month level panel regression: _exreti,t_ = _α_ + _β_ 1 �4 _j_ =1 _[exret][i,nm]_ [(] _[t,j]_ [)] [+]
_β_ 2( [�][4] _j_ =1 _[exret][i,nm]_ [(] _[t,j]_ [)] _[×]_ _[I]_ _t_ _[nm]_ ) + _β_ 3 _It_ _[nm]_ + _ϵi,t_ . Here _exreti,t_ is the value weighted return of industry _i_ in excess of the market
in month _t_, _exreti,nm_ ( _t,j_ ) is excess return in the _j_ th newsy month (Jan, Apr, Jul, Oct) preceding month _t_, and _It_ _[nm]_ is a dummy
variable indicating whether month _t_ is newsy. Column (1) and (2) perform the regression on the subsamples where the within
industry ROE connectivity is respectively low and high. Column (3) and (4) perform a similar exercise on low and high entry cost
industries. Column (5) and (6) are on unbalanced and balanced industries. Column (7) and (8) are on industries with a small
and larger number of stocks. 20 stocks are required in each industry-month, except for the last two columns, where no size filter
is applied. Data are monthly from 1971 to 2021 for columns 1-6, and from 1926 to 2021 for columns 7-8. T-stats computed with
standard errors clustered at the month level are reported in square brackets.


**Table** **14**


**Placebo** **test:** **no** **effect** **on** **fake** **‘industries’**


(1) (2)


unclassified random
�4 _j_ =1 _[exret][i,nm]_ [(] _[t,j]_ [)] -0.028 -0.003

[-0.77] [-0.49]
�4 _j_ =1 _[exret][i,nm]_ [(] _[t,j]_ [)] _[ ×][ I]_ _t_ _[nm]_ 0.065 0.005

[0.98] [0.47]


N 256 30,704


R-sq 0.010 0.000


This table reports results on the following ‘industry’-month level panel regression: _exreti,t_ = _α_ + _β_ 1 �4 _j_ =1 _[exret][i,nm]_ [(] _[t,j]_ [)] [+]
_β_ 2( [�][4] _j_ =1 _[exret][i,nm]_ [(] _[t,j]_ [)] _[×]_ _[I]_ _t_ _[nm]_ ) + _β_ 3 _It_ _[nm]_ + _ϵi,t_ . Here _exreti,t_ is the value weighted return of industry _i_ in excess of the market
in month _t_, _exreti,nm_ ( _t,j_ ) is excess return in the _j_ th newsy month (Jan, Apr, Jul, Oct) preceding month _t_, and _It_ _[nm]_ is a dummy
variable indicating whether month _t_ is newsy. Column (1) performs the regression on the ‘industry’ consisting of stocks with SIC
codes of 9910, 9990, 9999—which represent unclassified—and missing SIC code. Column 2 does the regression on the ‘industries’
represented by randomly generated SIC codes that takes on 30 values with equal probability. Data are from 1972 to 2021 for
column 1, and from 1926 to 2021 for column 2. 20 stocks are required in each industry-month. T-stats computed with standard
errors clustered at the month level are reported in square brackets.


**Table** **15**


**Newsyness** **of** **Q2** **in** **US** **across** **various** **half** **lives**


1 2 3 4 5 6 7 14 30 60


Apr 0.92 0.97 0.95 0.92 0.88 0.85 0.82 0.70 0.62 0.58


May 0.06 0.02 0.04 0.08 0.11 0.15 0.18 0.30 0.38 0.41


Jun 0.03 0.01 0.00 0.00 0.00 0.00 0.00 0.01 0.01 0.01


This table shows the value of quantitative newsyness of Q2 with various of half-life values for the aggregate market as of
2021.


**Table** **16**


**Quantitative** **newsyness** **and** **performance**


(1) (2) (3) (4)


Discrete 3-day 4-day 5-day


Panel A: US Industries excess returns


_β_ 1 0.042*** 0.058*** 0.062*** 0.066***


[3.84] [3.70] [3.68] [3.68]


_β_ 2 -0.061*** -0.125*** -0.133*** -0.142***


[-3.50] [-4.39] [-4.30] [-4.25]


N 19,108 14,748 14,748 14,748


R-sq 0.005 0.009 0.009 0.009


Panel B: Country excess returns


_β_ 1 0.087*** 0.038 0.052* 0.064**


[3.90] [1.53] [1.90] [2.18]


_β_ 2 -0.063** -0.070* -0.090* -0.103*


[-2.14] [-1.73] [-1.91] [-1.91]


N 19,062 5,570 5,570,5570


R-sq 0.004 0.007 0.007 0.007


Panel C: Country-Industries excess returns


_β_ 1 0.046* 0.038** 0.042** 0.045**


[1.74] [2.27] [2.29] [2.31]


_β_ 2 -0.068** -0.071** -0.078** -0.083**


[-2.17] [-2.09] [-2.04] [-2.01]


N 28,624 10,391 10,391 10,391


R-sq 0.004 0.004 0.004 0.004


In panel A, column 2-4 run the following industry-month level panel regressions with 3, 4,
and 5 day half-lives _exreti,t_ = _α_ + _β_ 1 _exret_ 12 _[nw]_ _i,t_ [+] _[ β]_ [2] _[exret]_ [12] _i,t_ _[nw]_ _[×][ New][i,t]_ [+] _[ β]_ [3] _[New][i,t]_ [+] _[ ϵ][i,t]_ [.]
Here _exreti,t_ is market cap weighted return of industry _i_ in excess of the market in month
_t_ . _Newi,t_ is the newsyness for industry _i_ in month _t_, and _exret_ 12 _[nw]_ _i,t_ [=] [�] _j_ [12] =1 _[exret][i,t][−][j]_ _[·]_
_Newi,t−j_ is the average excess return for industry _i_ over the past 12 months, weighted by
each month’s newsyness. Column 1 is the version of the regression with discrete, binary
newsyness, except the independent variable is scaled to have the same dispersion as _exret_ 12 _[nw]_ _i,t_
with 4-day half-life, so that the coefficients are roughly comparable across columns. Panel B
and C are analogous exercises with country level excess returns and country-industry level
excess returns. In panel A and C the regressions are weighted by the industry’s market cap
normalized by the cross section’s total market cap. Panel B uses equal weight. For column
2-4, data are monthly from 1973 to 2021 in panel A and 2000 to 2021 in B and C. The
later starting dates arises from the computation72 of the quantitative newsyness measures. Tstatistics computed with standard errors clustered at the month level are reported in square
brackets.


Electronic copy available at: https://ssrn.com/abstract=3480863


**Table** **17**


**Global** **company-fiscal** **period** **count** **by** **reporting** **month** **group**


Both filters Rpt Lag _<_ = 183 Group 3 FQ end No filter


Count Pct Count Pct Count Pct Count Pct


Group 1: Jan/Apr/Jul/Oct 168,568 19.76 222,976 22.94 173,502 19.94 228,720 23.07


Group 2: Feb/May/Aug/Nov 534,837 62.70 550,727 56.66 542,855 62.38 559,349 56.41


Group 3: Mar/Jun/Sep/Dec 149,654 17.54 198,271 20.40 153,906 17.68 203,448 20.52


Total 853,059 100 971,974 100.00 870,263 100.00 991,517 100.00


The table tabulates the number of company-quarter by 3 groups, where the groups are determined by the remainder of the
reporting month divided by 3. If a company reports earnings for a given fiscal quarter in October, this company-quarter
belongs to group 1, as 10 _≡_ 1 mod 3. First two columns contain count and percentage on the sample where 1) reporting
within 183 days and 2) aligned with calendar quarters. The next two columns do the same tabulation with only the first
filter. The next two columns apply only the second filter. The last two columns apply no filter. Data are quarterly and
semi-annually from 1998 to 2021.


**Table** **18**


**Lead-lag** **relations** **of** **monthly** **earnings** **in** **other** **countries**


(1) (2) (3) (4)


All NM Non-NM Difference


Panel A: Report Lag _≤_ 183 & Group 3 Month FQ end
�12 _j_ =1 _[roe][c,t][−][j]_ 0.015*** 0.013*** 0.043*** -0.031**

[4.08] [3.65] [3.52] [-2.39]


N 5,369 3,654 1,715 5,369


R-sq 0.048 0.046 0.096 0.060


Panel B: Report Lag _≤_ 183
�12 _j_ =1 _[roe][c,t][−][j]_ 0.012* 0.010* 0.041*** -0.031**

[1.78] [1.70] [3.11] [-2.15]


N 5,452 3,664 1,788 5,452


R-sq 0.052 0.044 0.170 0.072


Panel C: Group 3 Month FQ end
�12 _j_ =1 _[roe][c,t][−][j]_ 0.013*** 0.012*** 0.042*** -0.031**

[3.90] [3.45] [3.56] [-2.50]


N 5,382 3,659 1,723 5,382


R-sq 0.042 0.040 0.094 0.055


Panel D: No filter
�12 _j_ =1 _[roe][c,t][−][j]_ 0.012* 0.010* 0.041*** -0.031**

[1.78] [1.70] [3.16] [-2.18]


N 5,457 3,666 1,791 5,457


R-sq 0.049 0.042 0.159 0.068


Column 1 of this table reports results from the following country-month level panel regressions: _roec,t_ = _α_ + _β_ [�] _j_ [12] =1 _[roe][c,t][−][j]_ [+] _[ ϵ][c,t]_ [.] [Here] _[roe][c,t]_ [is] [the] [aggregate] [roe,] [or] [the] [aggregate]
net income before extraordinary items divided by aggregate book value of equity, of firms
reporting their earnings in month _t_ . It is then winsorized at the 10th and the 90th percentiles
per cross section. It is filled with a neutral value of zero when missing as part of the independent variable, but kept missing when used individually as the dependent variable. Column 2
and 3 report results from the same regression except on the subsample where the dependent
variables are newsy and non-newsy month returns, respectively. Column 4 reports the difference between column 2 and 3. Panel A aggregates ROE only on firm-quarters that are 1)
aligned with calendar quarters and 2) reporting within 183 days. Panel B applies only the
first filter; panel C only the second; panel D none. The regressions are weighted by aggregate
book value of equity of the country-month divided by the total book value of the year. Data
are monthly from 1998 to 2021. T-statistics computed with standard errors double clustered
at the month, country level are reported in square brackets.
74


Electronic copy available at: https://ssrn.com/abstract=3480863


**Table** **19**


**Lead-lag** **relations** **of** **monthly** **market** **returns** **in** **other** **countries**


(1) (2) (3) (4) (5) (6) (7)


All NM Non-NM All Post-WW2 First-Half Second-Half
�4 _j_ =1 _[mkt][c,nm]_ [(] _[t,j]_ [)] 0.010 -0.003 0.037*** 0.037*** 0.038** 0.025* 0.043**

[1.21] [-0.30] [2.77] [2.78] [2.55] [1.72] [2.28]
�4 _j_ =1 _[mkt][c,nm]_ [(] _[t,j]_ [)] _[ ×][ I]_ _t_ _[nm]_ -0.040** -0.041** -0.023 -0.049**

[-2.36] [-2.15] [-1.25] [-2.03]

_It_ _[nm]_ 0.007* 0.007 0.006* 0.007

[1.84] [1.61] [1.93] [1.26]


_const_ 0.009*** 0.011*** 0.004 0.004 0.005 0.004 0.004


[5.10] [5.23] [1.47] [1.47] [1.40] [1.45] [1.05]


N 19,477 12,980 6,497 19,477 16,665 7,201 12,276


R-sq 0.001 0.000 0.012 0.004 0.005 0.003 0.006


Column 1 of this table reports results from the following country-month panel regressions: _mktc,t_ = _α_ + _β_ [�] _j_ [4] =1 _[mkt][c,nm]_ [(] _[t,j]_ [)][+]
_ϵc,t_ . Here _mktc,t_ is the aggregate market return in month _t_ for country _c_, and _mktnm_ ( _t,j_ ) is the aggregate market return in
the _j_ th newsy “month” (Jan+Feb, Apr+May, Jul+Aug, Oct+Nov) preceding month _t_ for country _c_ . Column 2 reports
the same regression as in 1, but on the subsample where the dependent variable is returns of the newsy months. Column
3 is for the non-newsy months. Column 4 reports the difference between the coefficients in column 2 and 3, extracted
from a regression with additional interaction terms to _It_ _[nm]_, a dummy variable taking value 1 if month _t_ is newsy. Column
5-7 report results for the regression in column 4 on the subsamples of the post-WW2 period (1947-2021), the first half
(1926-1973), and the second half (1974-2021). Data are monthly from 1926 to 2021 for column 1-4. T-statistics computed
with clustered standard errors by month are reported in square brackets.


**Table** **20**


**Lead-lag** **relations** **of** **monthly** **market** **excess** **returns** **in** **other** **countries**


(1) (2) (3) (4) (5) (6) (7)


All NM Non-NM All Post-war First-Half Second-Half
�4 _j_ =1 _[exmkt][c,nm]_ [(] _[t,j]_ [)] 0.018*** 0.009 0.035*** 0.035*** 0.038*** 0.016 0.050***

[2.99] [1.23] [3.90] [3.90] [3.85] [1.19] [4.13]
�4 _j_ =1 _[exmkt][c,nm]_ [(] _[t,j]_ [)] _[ ×][ I]_ _t_ _[nm]_ -0.025** -0.029** -0.006 -0.043***

[-2.14] [-2.22] [-0.34] [-2.81]

_It_ _[nm]_ 0.002 0.002 0.004 0.001

[1.00] [0.99] [1.29] [0.25]


_const_ 0.002* 0.002** 0.000 0.000 0.000 0.002 0.000


[1.88] [2.14] [0.26] [0.27] [0.09] [0.81] [0.06]


N 19,062 12,692 6,370 19,062 16,444 6,899 12,163


R-sq 0.003 0.001 0.011 0.004 0.005 0.002 0.007


Column 1 of this table reports results from the following country-month panel regressions: _exmktc,t_ = _α_ +
_β_ [�] _j_ [4] =1 _[exmkt][c,nm]_ [(] _[t,j]_ [)] [+] _[ ϵ][c,t]_ [.] [Here] _[exmkt][c,t]_ [=] _[mkt][c,t]_ _[−]_ _[β]_ [ˆ] _c,t_ _[US]_ _−_ 1 _[mkt][US,t]_ _[−]_ [(1] _[ −]_ _[β]_ [ˆ] _c,t_ _[US]_ _−_ 1 [)] _[rf][t][−]_ [1][.] [It] [is] [the] [aggregate] [market] [re-]
turn in month _t_ for country _c_ subtract the US market return in month _t_ multiplied by country’s loading on the US return,
which is estimated on a rolling 24 months basis, and then subtract 1 minus this beta times the risk free rate. This
corresponds to a long-short portfolio return. Notice this beta estimate is available at the end of month _t −_ 1. _mktnm_ ( _t,j_ ) is
the aggregate market return in the _j_ th newsy “month” (Jan+Feb, Apr+May, Jul+Aug, Oct+Nov) preceding month _t_ for
country _c_ . Column 2 reports the same regression as in 1, but on the subsample where the dependent variable is returns
of the newsy months. Column 3 is for the non-newsy months. Column 4 reports the difference between the coefficients
in column 2 and 3, extracted from a regression with additional interaction terms to _It_ _[nm]_, a dummy variable taking value
1 if month _t_ is newsy. Column 5-7 report results for the regression in column 4 on the subsamples of the post war period
(1947-2021), the first half (1926-1973), and the second half (1974-2021). Data are monthly from 1926 to 2021 for column
1-4. T-statistics computed with clustered standard errors by month are reported in square brackets.


**Table** **21**


**Lead-lag** **relations** **of** **monthly** **industry** **excess** **earnings** **in** **other** **countries**


(1) (2) (3) (4)


All NM Non-NM Difference


Panel A: Report Lag _≤_ 183 & Group 3 Month FQ end
�12 _j_ =1 _[exroe][c,i,t][−][j]_ 0.023*** 0.019*** 0.073*** -0.054***

[4.68] [4.11] [7.64] [-5.17]


N 13,311 10,268 3,043 13,311


R-sq 0.055 0.046 0.167 0.078


Panel B: Report Lag _≤_ 183
�12 _j_ =1 _[exroe][c,i,t][−][j]_ 0.037*** 0.031*** 0.077*** -0.046***

[13.37] [11.57] [11.09] [-6.24]


N 17,737 12,315 5,422 17,737


R-sq 0.098 0.081 0.222 0.116


Panel C: Group 3 Month FQ end
�12 _j_ =1 _[exroe][c,i,t][−][j]_ 0.023*** 0.019*** 0.070*** -0.051***

[4.79] [4.23] [7.96] [-5.22]


N 13,740 10,582 3,158 13,740


R-sq 0.055 0.047 0.153 0.077


Panel D: No filter
�12 _j_ =1 _[exroe][c,i,t][−][j]_ 0.036*** 0.031*** 0.075*** -0.044***

[13.90] [12.01] [10.80] [-5.96]


N 18,244 12,678 5,566 18,244


R-sq 0.098 0.082 0.214 0.114


Column 1 of this table reports results from the following country-industry-month level panel
regressions: _exroec,i,t_ = _α_ + _β_ [�] _j_ [12] =1 _[exroe][c,i,t][−][j]_ [+] _[ ϵ][c,i,t]_ [.] [Here] _[exroe][c,i,t]_ [=] _[roe][c,i,t]_ _[−]_ _[roe][c,t]_ [,]
where _roec,i,t_ is the roe of industry _i_ of country _c_ in month _t_, or the aggregate net income
before extraordinary items divided by aggregate book value of equity, of firms of industry _i_ in
country _c_ reporting their earnings in month _t_, and _roec,t_ is the country-month aggregate roe.
It is then winsorized at the 10th and the 90th percentiles per cross section. It is filled with
a neutral value of zero when missing as part of the independent variable, but kept missing
when used individually as the dependent variable. Column 2 and 3 report results from the
same regression except on the subsample where the dependent variables are newsy and nonnewsy month returns, respectively. Column 4 reports the difference between column 2 and
3. Panel A aggregates ROE only on firm-quarters that are 1) aligned with calendar quarters
and 2) reporting within 183 days. Panel B applies only the first filter; panel C only the
second; panel D none. The regressions are weighted by aggregate book value of equity of the
country-month divided by the total book value of the year. 20 stocks are required for each

77

country-industry-quarter. Data are monthly from 1998 to 2021. T-statistics computed with
standard errors double clustered at the month, country level are reported in square brackets.


Electronic copy available at: https://ssrn.com/abstract=3480863


**Table** **22**


**Lead-lag** **relations** **of** **monthly** **industry** **excess** **returns** **in** **other** **countries**


(1) (2) (3) (4)


All NM Non-NM Difference


Panel A: SIC Major Group
�4 _j_ =1 _[exret][c,i,nm]_ [(] _[t,j]_ [)] 0.003 -0.007 0.024 -0.032*

[0.38] [-0.82] [1.51] [-1.72]


N 47,281 31,545 15,736 47,281


R-sq 0.000 0.000 0.005 0.002


Panel B: SIC Industry Group
�4 _j_ =1 _[exret][c,i,nm]_ [(] _[t,j]_ [)] -0.000 -0.016 0.031* -0.047**

[-0.03] [-1.59] [1.74] [-2.30]


N 34,383 22,925 11,458 34,383


R-sq 0.000 0.002 0.007 0.004


Panel C: SIC Industry
�4 _j_ =1 _[exret][c,i,nm]_ [(] _[t,j]_ [)] 0.000 -0.015 0.030* -0.045**

[0.04] [-1.33] [1.73] [-2.18]


N 28,622 19,087 9,535 28,622


R-sq 0.000 0.002 0.007 0.004


Column 1 of this table reports results from the following country-industry-month panel regressions: _exretc,i,t_ = _α_ + _β_ [�] _j_ [4] =1 _[exret][c,i,nm]_ [(] _[t,j]_ [)] [+] _[ ϵ][c,i,t]_ [.] [Here] _[exret][c,i,t]_ [,] [is] [the] [value] [weighted]
average return of industry _i_ in excess of the market of country _c_ in month _t_, and _exretc,i,nm_ ( _t,j_ )
is the excess return in the _j_ th newsy “month” (Jan+Feb, Apr+May, Jul+Aug, Oct+Nov)
preceding the month _t_ . Column 2 reports the same regression on the subsample where the
dependent variable is returns of the newsy months. Column 3 is for the non-newsy months.
Column 4 reports the difference between the coefficients in column 2 and 3, extracted from this
regression _exretc,i,t_ = _α_ + _β_ [�] _j_ [4] =1 _[exret][c,i,nm]_ [(] _[t,j]_ [)] [+] _[γ]_ [ �][4] _j_ =1 _[exret][c,i,nm]_ [(] _[t,j]_ [)] _[×]_ _[I]_ _t_ _[nm]_ + _δIt_ _[nm]_ + _ϵc,i,t_,
where _It_ _[nm]_ is a dummy variable taking value 1 if month _t_ is newsy. Panel A to C differ only
in the industry variable used. Regressions are weighted by the market cap of industry _i_ as
of the month _t −_ 1, normalized by the total market cap of the cross section. 20 stocks are
required in each month-country-industry. Data are monthly from 1986 to 2021. T-statistics
computed with clustered standard errors by month are reported in square brackets.


78


Electronic copy available at: https://ssrn.com/abstract=3480863


**Table** **23**


**Lead-lag** **relations** **of** **monthly** **market** **returns** **in** **US,** **by** **decades**


(1) (2) (3) (4) (5) (6) (7) (8) (9)


-1939 1940-49 1950-59 1960-69 1970-79 1980-89 1990-99 2000-09 2010�4 _j_ =1 _[mkt][nm]_ [(] _[t,j]_ [)] 0.239*** 0.041 0.107* 0.019 0.063 0.072 0.094 0.091 0.146**

[3.88] [0.52] [1.81] [0.28] [1.37] [1.52] [0.89] [1.41] [2.19]
�4 _j_ =1 _[mkt][nm]_ [(] _[t,j]_ [)] _[ ×][ I]_ _t_ _[nm]_ -0.408*** -0.138 -0.100 -0.085 -0.117 -0.263** -0.199 -0.209* -0.291***

[-3.76] [-1.17] [-1.05] [-0.77] [-1.05] [-2.22] [-1.45] [-1.75] [-2.80]

_It_ _[nm]_ 0.037* 0.005 0.008 0.015 0.000 0.014 0.011 -0.000 0.036***

[1.94] [0.56] [0.91] [1.28] [0.04] [1.33] [1.03] [-0.03] [3.12]


_const_ -0.011 0.008 0.006 0.003 0.007 0.009 0.009 0.001 -0.004


[-1.23] [1.47] [1.11] [0.43] [1.42] [1.44] [1.05] [0.28] [-0.57]


N 159 120 120 120 120 120 120 120 137


R-sq 0.114 0.009 0.029 0.022 0.018 0.063 0.026 0.040 0.069


Column 1 of this table reports results from the following monthly time-series regressions: _mktt_ = _α_ + _β_ 1 �4 _j_ =1 _[mkt][nm]_ [(] _[t,j]_ [)][ +]
_β_ 2 �4 _j_ =1 _[mkt][nm]_ [(] _[t,j]_ [)] _[ ×][ I]_ _t_ _[nm]_ + _β_ 3 _It_ _[nm]_ + _ϵt_ . Here _mktt_ is the US aggregate market return in month _t_, _mktnm_ ( _t,j_ ) is the return
in the _j_ th newsy month (Jan, Apr, Jul, Oct) preceding month _t_, and _It_ _[nm]_ is a dummy variable taking the value of 1
when month _t_ is newsy. The regression is done on different subsamples across columns. T-statistics computed with White
standard errors are reported in square brackets.


**Table** **24**


**Predicting** **US** **aggregate** **market** **returns** **with** **real** **time** **coefficients**


Method 0 1 2 3 4 5 6 7

_R_ [2] 0.49% 3.72% 3.60% 3.68% 3.97% 3.77% 3.82% 4.30%


            - _n_
_t_ =1 [(] _[r][t][−][r]_ [ˆ] _[t]_ [)][2]

The _R_ [2] in this table are calculated as 1 _−_ - _n_ _[r][t]_ [is the expanding window]

_t_ =1 [(] _[r][t][−][r][t]_ [)][2] [, where]
mean of past stock returns, and _r_ ˆ _t_ is the forecast being evaluated. This _R_ [2] is positive
only when the forecast outperforms the expanding window mean of past stock returns. Method 0 comes solely from Campbell and Thompson (2008) and functions as a
benchmark. It is the valuation constraint + growth specification with fixed coefficients.
Simple average is taken from the Dividend/Price, Earnings/Price, and Book-to-market
ratios based forecasts. Method 1 uses the signal that is simply the sum of past four
newsy month returns. The coefficients are extracted from simple expanding-window
OLS of past returns on past signals, separately for newsy and non-newsy month dependent variables. The signal used in method 2-7 is the sum of past four newsy month
returns, subtracting its expanding window mean, and sign flipped if the dependent
variable is a newsy month. Method 2 uses the same coefficient estimation method as in
method 1. Methods 3 replace the constant terms with the expanding window means of
past newsy and non-newsy month returns. Method 4 replace the constant terms with
the forecast in method 0. Method 5-7 are method 2-4 with the coefficients estimated
on the combined sample of newsy and non-newsy months. Data are monthly from 1926
to 2021.


80


Electronic copy available at: https://ssrn.com/abstract=3480863


Figure 1: Timing of independent and dependent variables in return forecasting regressions, US


This figure shows how the independent variables in the US return forecasting regressions progress as the dependent variable
move forward.


Figure 2: Next month’s market returns vs past four newsy month returns, by whether
the next month is newsy



This figure plots mean of US monthly aggregate market returns in the next month
against total returns during past four newsy months. The newsy months are the first
months of the calendar quarters, namely January, April, July, and October. The sample
is split based on whether the next month is newsy. Data are monthly from 1926 to
2021. One arm of the error bars represents 2 standard errors.


82


Electronic copy available at: https://ssrn.com/abstract=3480863


Figure 3: Autoregressive coefficients of US monthly aggregate market returns







This figure shows the autoregressive coefficients of US monthly aggregate market returns. The dotted line is a trend line on the coefficient values over lags. Data are
monthly from 1926 to 2021. The error bars represented 2 standard errors.


83


Electronic copy available at: https://ssrn.com/abstract=3480863


Figure 4: Distance in calendar and fiscal time of lagged data in an earnings forecasting setting


This figure shows the dependent and independent variables used by a hypothetical investor trying to forecast the earnings
in each calendar month using past earnings. It demonstrates that past earnings contained over the same look-back window
in terms of calendar time are actually further away in terms of fiscal time—which is what determines the nature of the
news—if the dependent variable is in a newsy month. Fiscal periods corresponding to earnings reported in each calendar
month are labeled and color coded.


# **Appendix** **A Correlation neglect and evidence**

In short, the effect of correlation neglect says that if investors get two consecutive

signals with the second being a thinly-veiled repetition of the first, agents then overreact

to the second signal. This overreaction subsequently corrects itself. In the setting of the

earnings reporting cycle, if we think of the first signal as aggregate earnings announced

in the first month of quarter, and the second as that announced in the second month,

correlation neglect then predicts that 1) the first month return positively predicts the

second month return and 2) the second month return negatively predicts the return in

the first month of the next quarter.

A major distinction between that and the main result documented in this paper are

noteworthy: It is the _second_ month return that negatively predicts future returns. The

main result instead uses the first month return to negatively predict future returns.

In other words, in the correlation neglect setting the second month is the time of

overreaction. In the main result the first month contains both under and over-reaction.

Notice that correlation neglect does not explain why the first month return is pos
itively predicting returns in the second and the third months of the next quarter and

beyond. It also does not explain why the first month return is negatively predicting

returns in the first month of the next quarter and beyond. Correlation neglect therefore

differs from my story in two ways: it makes additional predictions, and at the same

time does not make some predictions that my story makes. I therefore am documenting

evidence in favor of correlation neglect in this appendix, so that the two effects can be

separated and distinguished.

I document the evidence supporting correlation neglect in Table A1. Column 1

shows that aggregate market return in the second months of the quarters negatively

predicts returns in the first month of the next calendar quarter. Column 2 shows

that industry level return in excess of the market in the second month of the quarter

negatively predicts the excess return in the first month of the next quarter and the

quarter afterward. These are precisely what correlation neglect predicts.

An immediate next step prediction here is that this reversal is substantially stronger

when the signals in the first month and the second month agreed. If one measure

the degree of agreement using the product of the first and the second month returns


85


Electronic copy available at: https://ssrn.com/abstract=3480863


this prediction does not pan out. It could be that we need a better measurement

of agreement, however. Overall, the evidence here is interesting but we need more

investigations to make a convincing case.


86


Electronic copy available at: https://ssrn.com/abstract=3480863


**Table** **A1**


**Evidence** **supporting** **correlation** **neglect**


(1) (2)


market return industry exret


_β_ 2 -0.275*** -0.110**


[-3.05] [-2.63]


_β_ 5 0.040 -0.081**


[0.73] [-2.08]


_β_ 8 0.140 -0.001


[1.31] [-0.02]


_β_ 11 -0.072 0.041


[-0.94] [1.30]


N 378 6,131


R-sq 0.091 0.017


Column 1 shows results from the following monthly time-series regression: _mktt_ =
_α_ + _β_ 2 _mktt−_ 2+ _β_ 5 _mktt−_ 5+ _β_ 8 _mktt−_ 8+ _β_ 11 _mktt−_ 11+ _ϵt_, conditioning on month _t_ is a newsy
month. Here _mktt_ is aggregate market return in month _t_, and _mktt−x_ is aggregate
market return _x_ months before month _t_ . It shows how the market returns in the newsy
months are being predicted by past second months of the quarter. For instance, if
the dependent variable is the return of October, the independent variables are returns
of August, May, February, and November of the previous year. The second column
does an analogous regression on an industry-month panel: _exreti,t_ = _α_ + _β_ 2 _exreti,t−_ 2 +
_β_ 5 _exreti,t−_ 5 + _β_ 8 _exreti,t−_ 8 + _β_ 11 _exreti,t−_ 11 + _ϵi,t_ . T-stats are reported in square brackets.
Data are monthly from 1926 to 2021. In the first column, White standard errors are
used to compute the t-stats. In the second column, standard errors clustered at the
monthly level are used.


87


Electronic copy available at: https://ssrn.com/abstract=3480863


# **B Alternative versions of the models**

## **B.1 Earnings surprises and returns**

In the data, aggregate earnings surprises and aggregate market returns have only a

small positive correlation around 0.1. Related, the correlation at the stock level is

not too strong either. This pattern can potentially arise from investors’ correct un
derstanding that part of the cash flow surprise is temporary. The intuition can be

reflected in my model, which I compactly summarize below. Let ∆ _dt_ +1 = _dt_ +1 _−_ _bt_,
where _bt_ = [�] _j_ _[∞]_ =0 _[ρ][j][d][t][−][j]_ [,] [as] [before.]
Investors’ beliefs:


∆ _dt_ +1 = _yt_ +1 + _ut_ +1


_iid_
_ut_ +1 _∼_ _N_ (0 _, σu_ ) _,_ _∀t_


_yt_ +1 = _mxt_ + _vt_ +1



_xt_ =



_∞_


_δ_ _[j]_ _yt−j_

_j_ =0



Notice that investors correctly understand that _ut_ is purely temporary and does not

impact future cash flow growth, even though it entered past cash flow growth. This

leads to a two-state-variable solution for the valuation ratio as before:


_Pnt_

= _e_ _[a][n]_ [+] _[b][n][x][t]_ [+] _[c][n]_
_Dt_


where:



_an_ = _an−_ 1 + log _r_ + [(] _[b][n][−]_ [1][ +] _[ c][n][−]_ [1][ + 1)][2]




_[n][−]_ [1][ + 1)][2]

_σv_ [2] [+] [(] _[c][n][−]_ [1][ + 1)][2]
2 2



2 _σu_ [2]



_bn_ = ( _m_ + _δ_ ) _bn−_ 1 + (1 + _cn−_ 1) _m_


_cn_ = _−ρ_


This set of valuation, combined with the realization of:


88


Electronic copy available at: https://ssrn.com/abstract=3480863


_yt_ +1 =








 _hxt_ + _vt_ +1 _,_ where _t_ is even


 _lxt_ + _vt_ +1 _,_ where _t_ is odd



_lxt_ + _vt_ +1 _,_ where _t_ is odd



Leads to returns:


log(1 + _Rn,t_ +1) = _an−_ 1 _−_ _an_ + ( _h −_ _m_ )( _bn−_ 1 + 1 _−_ _ρ_ ) _xt_ +


_bn−_ 1 _vt_ +1 + (1 _−_ _ρ_ )( _vt_ +1 + _ut_ +1) _,_ where _t_ is even


log(1 + _Rn,t_ +1) = _an−_ 1 _−_ _an_ + ( _h −_ _m_ )( _bn−_ 1 + 1 _−_ _ρ_ ) _xt_ +


_bn−_ 1 _vt_ +1 + (1 _−_ _ρ_ )( _vt_ +1 + _ut_ +1) _,_ where _t_ is odd


Notice that _ut_ +1 and _vt_ +1 equally enter ∆ _dt_ +1. However, due to the multiplier _bn−_ 1,

_vt_ +1 is much more important than _ut_ +1 as a component of the returns. This is because

_vt_ enters _xt_ and thus influences valuation, while _ut_ does not.

## **B.2 Past cash flow growth unevenly enters valuation**


We see that aggregate market returns in the newsy months are mainly responsible for

predicting future returns. In our previous versions of the models, both kinds of past

returns positively predict future non-newsy months returns, and negatively predict

future newsy months returns. A potential explanation for this distinction from the

independent variable’s perspective is that investors re-form their earnings forecasts

mainly around earnings seasons. The intuition can be added in my model, which I go
over below. Let ∆ _dt_ +1 = _dt_ +1 _−_ _bt_, where _bt_ = [�] _j_ _[∞]_ =0 _[ρ][j][d][t][−][j]_ [,] [as] [before.]
Investors’ beliefs:


∆ _dt_ +1 = _mxt_ + _ut_ +1


_iid_
_ut_ +1 _∼_ _N_ (0 _, σu_ ) _,_ _∀t_



_xt_ =









- _∞j_ =0 _[δ][j]_ [∆] _[d][t][−]_ [2] _[j]_ where _t_ is odd

- _∞j_ =0 _[δ][j]_ [∆] _[d][t][−]_ [2] _[j][−]_ [1] where _t_ is even







Notice only the odd period ∆ _dt_ enters _xt_ . This then leads to the following iteration


89


Electronic copy available at: https://ssrn.com/abstract=3480863


rule:



_xt_ =








( _m_ + _δ_ ) _xt−_ 1 + _ut_ where _t_ is odd


 _xt−_ 1 where _t_ is even



_xt−_ 1 where _t_ is even



These together lead to a two-state-variable form for the valuation ratio as before,

except that now there is a superscript indicating an additional dependence on whether

_t_ is even or odd:



_Pnt_

=
_Dt_








 _e_ _[a]_ _n_ [1] [+] _[b]_ [1] _n_ _[x][t]_ [+] _[c]_ [1] _n_ where _t_ is odd


 _e_ _[a]_ _n_ [0] [+] _[b]_ [0] _n_ _[x][t]_ [+] _[c]_ [0] _n_ where _t_ is even



_e_ _[a]_ _n_ [0] [+] _[b]_ [0] _n_ _[x][t]_ [+] _[c]_ [0] _n_ where _t_ is even



The iteration rules are:


When _t_ is even:



_n−_ 1 [+ 1)][2]
_a_ [1] _n_ = _a_ [0] _n−_ 1 [+ log] _[ r]_ [ +] [(] _[c]_ [0] _σu_ [2]

2

_b_ [1] _n_ = _b_ [0] _n−_ 1 [+ (1 +] _[ c]_ _n_ [0] _−_ 1 [)] _[m]_

_c_ [1] _n_ = _−ρ_



_n−_ 1 [+] _[ c]_ _n_ [1] _−_ 1 [+ 1)][2]
_a_ [0] _n_ = _a_ [1] _n−_ 1 [+ log] _[ r]_ [ +] [(] _[b]_ [1] _σu_ [2]

2



_b_ [0] _n_ = ( _m_ + _δ_ ) _b_ [1] _n−_ 1 [+ (1 +] _[ c]_ _n_ [1] _−_ 1 [)] _[m]_

_c_ [0] _n_ = _−ρ_


Along with the initial condition that _a_ [1] 0 [=] _[ b]_ 0 [1] [=] _[ c]_ 0 [1] [=] _[ a]_ 0 [0] [=] _[ b]_ 0 [0] [=] _[ c]_ 0 [0] [= 0,] [all] _[a]_ [,] _[b]_ [,] [and]
_c_ can be solved. In particular,



_n−_ 1
1 _−_ ( _m_ + _ρ_ ) 2 2 _m_ (1 _−_ _ρ_ ) + _m_ (1 _−_ _ρ_ ) where _n_ is odd

1 _−m−ρ_

_n_
1 _−_ ( _m_ + _ρ_ ) 2 where _n_ is even
1 _−m−ρ_ [2] _[m]_ [(1] _[ −]_ _[ρ]_ [)]


90



_b_ [1] _n_ =











Electronic copy available at: https://ssrn.com/abstract=3480863


_n−_ 1
1 _−_ ( _m_ + _ρ_ ) 2 2 _m_ (1 _−_ _ρ_ )( _m_ + _δ_ ) + _m_ (1 _−_ _ρ_ ) where _n_ is odd

1 _−m−ρ_

_n_
1 _−_ ( _m_ + _ρ_ ) 2 where _n_ is even
1 _−m−ρ_ [2] _[m]_ [(1] _[ −]_ _[ρ]_ [)]



_b_ [0] _n_ =











These then lead to the following returns:



log(1 + _Rn,t_ +1) =








 _a_ [0] _n−_ 1 _[−]_ _[a]_ _n_ [1] [+ (] _[h][ −]_ _[m]_ [)(1] _[ −]_ _[ρ]_ [)] _[x][t]_ [+ (1] _[ −]_ _[ρ]_ [)(] _[u][t]_ [+1][)] where _t_ is odd

 _a_ [1] _[−]_ _[a]_ [0] [+ (] _[l][ −]_ _[m]_ [)(] _[b][n][−]_ [1] [+ 1] _[ −]_ _[ρ]_ [)] _[x][t]_ [+ (] _[b][n][−]_ [1] [+ 1] _[ −]_ _[ρ]_ [)] _[u][t]_ [+1] where _t_ is even



_a_ [1] _n−_ 1 _[−]_ _[a]_ _n_ [0] [+ (] _[l][ −]_ _[m]_ [)(] _[b][n][−]_ [1] [+ 1] _[ −]_ _[ρ]_ [)] _[x][t]_ [+ (] _[b][n][−]_ [1] [+ 1] _[ −]_ _[ρ]_ [)] _[u][t]_ [+1] where _t_ is even



Notice the predictable component of stock returns depends on _xt_ as before. Because
only the low realization periods, or newsy periods cash flow growth enters _xt_, only

returns in those periods will positively and negative predict future non-newsy and

newsy periods returns, respectively.


91


Electronic copy available at: https://ssrn.com/abstract=3480863


# **C Trading strategies, Sharpe ratios, and alphas**

## **C.1 Time series**

I convert the return predictability patterns that I document into trading strategies

implementable in real time. Coefficients obtained by regressing future returns on sig
nals, like those documented in Table 4 and Table 11, are in principle returns to long
short portfolios themselves (Fama and MacBeth (1973)). [30] Hence the results in this

section is to some extent already implied by my return predicting results. However,

the implied portfolios often have look-ahead bias in their weights and are technically

not implementable in real time. Out of an abundance of caution, in this section I form

portfolios with information available in real time, and compute its Sharpe ratio and

multi-factor alphas.

Starting the aggregate market strategy, at the end of each month _t −_ 1 I take the

total returns of the aggregate market in the past four newsy months (potentially include

month _t −_ 1), and compute its expanding window mean, which is the average from the

beginning of the sample to month _t−_ 1. I then take the difference, and flip sign if month

_t_ is newsy to arrive at the demeaned signal _xt−_ 1. I then run a constrained time-series

regression _mktt_ = _βxt−_ 1 + 1 _mktt−_ 1 + _ϵt_, where _mktt_ is the market return in month

_t_, _xt−_ 1 is the said demeaned signal, and _mktt−_ 1 is the expanding window mean of the
market return up to month _t −_ 1. Notice the coefficient before _mktt−_ 1 is constrained

to be 1. Denote estimated coefficient _β_ as _ct_ . The forecasted market return at the end

of month _t_ for month _t_ + 1 is then _ctxt_ + _mktt_ . The portfolio weight in my strategy
is _ctxt_, which roughly has a mean of zero over time. Lastly, the portfolio is scaled by

a constant so that it has the same volatility as the aggregate market, which is 5.34%
per month. [31] This is so that the portfolio’s average return is in comparable unit as the


30Consider the simplest case where you do a cross sectional regression of returns on one signal
and a constant. Denote the returns as the vector ( _r_ 1 _, r_ 2 _, ..., rn_ ) and the signal ( _x_ 1 _, x_ 2 _, ..., xn_ ). The

         - _ni_ =1 [(] _[x][i][−][x]_ [)(] _[r][i][−][r]_ [)] _xi−x_

coefficient on the signal is then - _ni_ =1 [(] _[x][i][−][x]_ [)][2] = [�] _i_ _[n]_ =1 - _ni_ =1 [(] _[x][i][−][x]_ [)][2] _[r][i]_ [,] [where] _[r]_ [and] _[x]_ [are] [the] [cross]

sectional means of _r_ and _x_ . Notice this coefficient value is the return to a portfolio of stocks, with
_xi−x_
the weight on stock _i_ being - _n_ [.] [Notice] [this] [weight] [sums] [to] [0,] [and] [the] [portfolio] [is] [hence] [long]
_i_ =1 [(] _[x][i][−][x]_ [)][2]
short. Additionally, the weight ensures that the portfolio has unit exposure to the signal itself, i.e.

- _n_ _xi−x_
_i_ =1   - _ni_ =1 [(] _[x][i][−][x]_ [)][2] _[x][i]_ [=] [1,] [and] [therefore] [the] [scale] [of] [the] [portfolio] [is] [often] [not] [meaningful] [unless] [the]
signal is in interpretable unit. The Sharpe ratio of the portfolio is always meaningful though.
31One may argue that this scaling, even though it does not change the portfolio’s Sharpe ratio,
still has look-ahead bias in it, because the number 5.34% is not known in advance. This can similarly
be dealt with using an expanding window approach, and it leads to similar results.


92


Electronic copy available at: https://ssrn.com/abstract=3480863


aggregate stock market.

Table C1 regresses the said time-series portfolio returns on a constant and contem
poraneous factors, including the market, value, size, and momentum. The coefficients

on the constant are of interest. In column 1, the coefficient of 0.823 means that the

portfolio has an average return of 0.823% per month, which is about 10% per annum.

This corresponds to an annualized Sharpe ratio of 0.44, which is about the same as

that on the aggregate market. It is worth noticing that explaining the sheer scale of

this Sharpe ratio is non-trivial when the underlying instrument is just the aggregate

market: the equity premium puzzle (Mehra and Prescott (1985)) inspired sophisticated

models developed by generations of scholars (e.g. Abel (1990)), Constantinides (1990),

Campbell and Cochrane (1999), Bansal and Yaron (2004), Rietz (1988), Barro (2006),

Gabaix (2012), Wachter (2013)). Therefore the predictability I document is worth

thinking carefully about.

In column 2, we see that the strategy is indeed roughly market neutral, as designed.

It leads to a CAPM alpha of about 0.75% per month. In column 3 and 4 we see that

the 3-factor and 4-factor alphas of this strategy are 0.64% and 0.74% per month. It is

worth noting that even though my trading strategy involves substantial rebalancing,

the underlying instrument is the aggregate market, and the incurred trading cost is

likely lower than strategies that require stock level rebalancing, such as the value, size,

and the momentum factors.

## **C.2 Cross sectional**


Having discussed the time series strategy I now move to the cross sectional strategy

trading on US industries. For each industry _i_ and month _t_, I compute _i_ ’s total excess

return of the past four newsy months, and then cross sectionally demean with market

cap weight at the end of month _t_ . I then flip the sign of this total excess return if month

_t_ +1 is newsy to arrive at the signal _xi,t_ . I then compute a expanding window standard

deviation _σt_ of the signal _x_ across all industry-month up to month _t_, weighting by

market cap divided by the total market cap of the cross section. The portfolio weight

is _xi,t/σt_ winsorize at [-2, 2] to make sure no extreme position is taken. Lastly, the

portfolio is then scaled so that it has the same volatility as the aggregate market excess

return, which is 5.34% per month. Notice this strategy is market neutral in each cross

section.

Table C2 regresses this cross sectional portfolio returns on the market, value, size,


93


Electronic copy available at: https://ssrn.com/abstract=3480863


and momentum factors. Column 1 shows that the average return of this portfolio is

about 0.62% per month, and the annualized Sharpe ratio is about 0.33. Across the

rows we see that the multi-factor alphas of this strategy is strongly positive, even

though it declines as factors are added in, because it has small positive loadings on

the size and the momentum factors. It is worth noting that the factor’s loading on the

momentum factor is not very strong. This is because it bets against continuation one

third of the times, and it is at the industry level and uses only newsy month returns

as the predictors. Overall, this shows that the cross sectional return predictability I

document can also be translated into a trading strategy.


94


Electronic copy available at: https://ssrn.com/abstract=3480863


**Table** **C1**


**Time** **series** **strategies** **and** **alphas**


(1) (2) (3) (4)


_ts_ ~~_p_~~ _ft_ _ts_ ~~_p_~~ _ft_ _ts_ ~~_p_~~ _ft_ _ts_ ~~_p_~~ _ft_
_MKTt −_ _Rft−_ 1 0.110 -0.021 -0.046


[0.88] [-0.25] [-0.57]


_HMLt_ 0.361** 0.309*


[2.14] [1.88]


_SMBt_ 0.391 0.386


[1.29] [1.25]


_MOMt_ -0.112


[-1.07]


_const_ 0.823*** 0.748*** 0.635*** 0.743***


[4.29] [4.34] [3.83] [3.90]


N 1,136 1,136 1,136 1,134


R-sq 0.000 0.008 0.082 0.087


Column 1 shows results from the following monthly time-series regression: _ts_ _pft_ =
_α_ + _ϵt_ . Here _ts_ _pft_ is our time-series portfolio return in month _t_ . This portfolio longs
or shorts the aggregate market for a given month, and the weight is proportional to the
previous-month-end forecasted market return subtracting the expanding window mean
of aggregate market returns and scaled to have the same volatility as the aggregate
market excess return, which is 5.34% per month. The said forecasted market return is
constructed with the following steps: 1) demean the total return of the past four newsy
months (January, April, July, and October) with the expanding window mean; 2) flip
sign if the next month is newsy to arrive at our signal; 3) regress the aggregate market
return on lag one month signal and the expanding window mean aggregate market
return based on data available in real time at each month, and with the coefficient
on the expanding window mean aggregate market return constrained to 1; 4) compute
the forecast as the coefficient estimated at a given month times the signal plus the
expanding window mean aggregate market return. Notice the forecast is designed
to use only data available in real time. Column 2-4 add in the market, value, size,
and momentum factor returns on the right hand side. In column 1, the coefficient of
the constant represents the average return of time-series portfolio. In column 2-4 it
represents its alphas with different factor models. Data are monthly from 1926 to 2021.
Returns are all in percentage unit. T-stats computed with White standard errors are
reported in the square brackets.

95


Electronic copy available at: https://ssrn.com/abstract=3480863


**Table** **C2**


**Cross** **sectional** **strategies** **and** **alphas**


(1) (2) (3) (4)


_cs_ ~~_p_~~ _ft_ _cs_ _pft_ _cs_ ~~_p_~~ _ft_ _cs_ ~~_p_~~ _ft_
_MKTt −_ _Rft−_ 1 -0.026 -0.067 -0.054


[-0.73] [-1.46] [-1.14]


_HMLt_ 0.001 0.028


[0.01] [0.29]


_SMBt_ 0.211* 0.214*


[1.79] [1.81]


_MOMt_ 0.057


[0.69]


_const_ 0.619*** 0.638*** 0.621*** 0.566***


[3.89] [3.98] [3.90] [3.27]


N 1,136 1,136 1,136 1,134


R-sq 0.000 0.001 0.015 0.017


Column 1 shows results from the following monthly time-series regression: _cs_ ~~_p_~~ _ft_ =
_α_ + _ϵt_ . Here _cs_ _pft_ is our cross-sectional portfolio return in month _t_ . This portfolio takes
long and short positions on industries in a given month, and the weight is constructed
with the following steps: 1) for each industry-month, compute the total excess return of
the past four newsy months (January, April, July, and October), and cross sectionally
demean with market cap weight; 2) flip sign if the next month is newsy; 3) scale by
expanding window standard deviation of the signal, and winsorize at [-2, 2] to make
sure no extreme position is taken. The portfolio is then scaled so that it has the same
volatility as the aggregate market excess return, which is 5.34% per month. Column
2-4 add in the market, value, size, and momentum factor returns on the right hand side.
In column 1, the coefficient of the constant represents the average return of time-series
portfolio. In column 2-4 it represents its alphas with different factor models. Data are
monthly from 1926 to 2021. Returns are all in percentage unit. T-stats computed with
White standard errors are reported in the square brackets.


96


Electronic copy available at: https://ssrn.com/abstract=3480863



Name of student: Panel data econometrics homework: replication

- To be uploaded on the EPI at the due date

- The original paper in pdf

- The database that you use (possibly updated with respect to the paper), possibly in Excel format.

- The database formatted for the software you used (Python, Stata, R)

- The code of your preferred software (e.g. Python), in a format so that anyone can run your code immediately.

- The code translated in Stata and R with the help of LLM, with comments mentioning difficulties for running these versions.

- A Word or TEX and pdf version of your answers according to the guidelines starting next page (using this word file or copied in TEX).

- A Word and then a PDF file with copy and paste of all your LLM prompts and answers for doing this homework, including code (no problem if it is 300 pages).

- A “To-do-list” of steps of panel data for the next time you will use panel data.

You may add a commented HTML file of the code and output of your software, but it is NOT accepted to be a substitute of the written version of answers. Some panel data estimates (in particular, GMM, with xtabond2, Hausman Taylor) are coded in STATA. A book with R code for panel data is in the folder BOOKS.

> **Remark:** If ever you estimate an autoregressive parameter (or the sum of the auto-regressive parameters) which is larger than one, the series of the long run coefficients are infinite and the formula with $1/(1-\rho)$ is not valid. One can compute the impulse response for the first periods, but they explode.

> **Remark:** Pay attention: is your work readable? Copy and paste patchy answers from LLM is not enough for readability. The reader at the end may not grasp anything of what you did not yourself understood. The aim of statistics is to extract signal from noise and explain it clearly. You may have a perfect “to do list” proposed by LLM which contradicts what you have written.

---

Homework Panel data: Partial replication

**Name of the student:** **APA Reference of the replicated paper using Google Scholar and check:** (authors, title, journal, pages) **Link to the paper (possibly with DOI):**

**Table 1: Key correlation of the paper**

| Dependent variables denoted Y in what follows

| Name and link to the website of data source for updates:

| Key preferred explanatory variables denoted X in what follows

| Name and link to the website of data source for updates:

| |
| |

| Select the level(s): country, sectors, firm, bank, households, assets of financial markets

| | | |

**Link to the data set:** **Links to the data set sources:**

**Abstract** (100 words) of what you have done. **Introduction** (1 page): summarize in 3 paragraphs what you find which was not seen in the paper (to do at the end of your partial replication)

**Table 2: Key items found by order of interest of this partial replication**

| Item Rank |
| --------- |

| 1

|
| 2

|
| 3

|
| 4

|
| 5

|

Database update

If the data set can be updated by the recent years from freely publicly available database, update it. Precise if updates of variables with observations different from the original database (GDP can be updated by national accountants for recent years), if you add variables, if you add individuals (countries for example). Mention any issue with the available original database: incomplete with respect to paper, if sent by the authors upon your request.

**Table 3: Data characteristics**

| Maximal time span

| Frequency

| Number of individuals

| Maximal number of time observations for an individual

| Balanced or unbalanced panel

| |
| |

| 2020Q2-2022Q3

| Quarterly

| Ntotal=76

| Tmax= For individual "Germany"

| Balanced

|
| Update: 2022Q4-2024Q4

| | Ntotal=

| Tmax=

| |

Panel data sample selection

**Table 3: Sample selection for dynamic panel data: at least 3 consecutive observations of the DEPENDENT variable for each individual.** You could have missing data in between (for a given individual, 3 years consecutive, 2 years missing, then again 3 years consecutive). You replace non-consecutive observations or two consecutive observations only of the dependent variable for a given individual which remains in the sample with 3 other consecutive observations on other dates by “not available” or “.” for the dependent variable. [The point is to stick to descriptive statistics matching the maximal sample for the estimation of the dependent variable]

> **Remark:** For within, at least two consecutive observations are needed but we prefer to have at least 3 consecutive observations in order to regress first differences on first differences and use Anderson-Hsiao estimator for the benchmark sample, because so many economic variables are persistent (autocorrelated) so that a lagged dependent variable needs to be included at least in robustness checks for a dynamic model. Within transformation faces a large Nickell’s (1981) bias on the parameter of the lagged dependent variable for T small.

**Panel data sample selection**

| Individuals excluded from the panel data selection

| Individuals with at least THREE consecutive observations for the dependent variable : these are the individuals kept in all the next questions

| |
| |

| Number: N1=

| Ntotal-N1=N

|
| | Maximal time span for an individual: (example) 2016-2020 yearly

|
| List:

| List:

|

Comment the panel data sample selection bias: Are small firms, poor countries or some major country excluded because of missing observations of the dependent variable?. From now on, ALL the statistics are only computed on this selected panel data sample asking statistics with a restriction (if dependent variable non equal to “not a number” or “.”).

Sample selection within an unbalanced panel

Data availability often implies sample selection leading to unbalanced panel (missing time observations for some individuals).

**Table: number of individuals per date**

| Date

| 2010

| 2011

| 2012

| …

|     |     |     |     |
| --- | --- | --- | --- |

| N

| 10

| 30

| | | | | | |

Do a graph of the number of observations if more than 30 periods. Comment on attrition (less observations) at the beginning and at the end and comment).

**Table: Number of individuals with the same number of temporal observations**

| Observations By individuals

| Tmax

| Tmax-1

| Tmax-2

| …

| | | | 4

| 3

| |
| |

| Number of individuals in this case

| 10

| 30

| 50

| | | | | 90

| 100

|

Give the number and the proportion of individuals with holes (discontinuity with missing observations) and give their list if below 100. Comment if there is a pattern for this unbalanced panel sample selection: small firms, poor countries?

Panel data variables classification

Compute between transformed and one-way-within transformed variables for all variables. Compute their variance and the share of within variance in the overall variance. Sort the variables by their share of within variance. THEN, split the variables in 3 categories: 100% within (common time series to all individuals), 0% < share of within < 100%: double indices, the closer to 100%, the closer to common time series, the closer to 0%, the closer to time-invariant variables. Report the information in the next 4 tables and comment each table.

**Table 4: Variable count by categories**

| List of variables varying with two indices (time and individuals).

| List of time invariant variables (share of between variance 100%), wiped out by individual dummies

| List of individual invariant variables. (time series invariant for all individuals), wiped out by time dummies

| |
| |

| Number: K=

| K1=

| K2=

|

**Table 5: Time varying variables (0%<%within variance< 100%)**, the variables should by sorted by their percentage of within variance (from the highest within variance down to the lowest).

| Variable (in words)

| N

| NT

| NT/N

| Overall variance

| Between variance

| Within Variance

| % within variance/ Total

| Sorted by this column

| |
| |

| Dependent variable(s) first

| | | | | | | | |
| Explanatory variable ordered by % of within variance.

| | | | | | | | |

Comment the relative share for the key dependent and key explanatory variables of interest. A small share of within variance may correspond to small within variance as if the variable is nearly time-invariant. By contrast, high within variance may be related to a couple of high leverage observations of opposite sign after within transformation.

**Table 4: Time invariant variables (100% between variance)**

| Variable (in words)

| N

| NT

| NT/N

| Overall variance

| Between variance

| Within variance

| % within variance

|     |
| --- | --- | --- | --- | --- | --- | --- |
|     |     |     |     |     |     | 0   |

| 0%

|

**Table 5: Individual invariant variables (0% between variance)**

| Variable (in words)

| N

| NT

| NT/N

| Overall variance

| Between variance

| Within variance

| % within variance

|     |
| --- | --- | --- | --- | --- | --- |
|     |     |     |     |     | 0   |

| | 100%

|

The number of observations matters, because some explanatory variable have less observations than the dependent.

Between plus One-Way Within decomposition: univariate bivariate descriptive statistics after variable transformations

Plot the distribution of the one-way-fixed-effects-within x(it)-x(i.) and between (x(i.)) transformed dependent variable and of you key (preferred) explanatory variable (not all the explanatory variable) plotting on the same graph an histogram, a normal law with same empirical mean and standard error and a kernel continuous approximation. Comment the between and within difference for each variable, and compare within/within for dependent and explanatory variable, and between/between for dependent and explanatory variable: kurtosis, skewness, non-normality, high leverage observation (far from the mean), several modes (mixture of distribution)? First differences versus two-way fixed effects univariate and bivariate descriptive statistics after variable transformations (they eliminate deterministic trends).

FIRST DIFFERENCE VARIABLE TRANSFORMATIONS: Compute the first-differences x(i,t)-x(i,t-1) for panel data. Check for the first 3 changes of individuals (for data sorted by individual and then time) in say 3T+1 first observations that when there is a change of individual in the stacked vector individuals x time, the first differences is a dot for “not available”. In other words, for first-differences for panel data, check that when you change individual, the first observation is missing with a dot, and it is not the difference of the first observation of the second individual minus the last observation of the first individual, for example.

First differences distributions. Plot the distributions (histogram, KDE, normal law with same mean and standard error) for first difference dependent Y and first difference explanatory X for each of these two transformations. First differences simple correlation. For these FD transformed variables, plot the bivariate cloud of points with regression line and on top the marginal distribution of the horizontal axis and on right hand side the marginal distribution of the variable on the vertical axis. Compare with one-way-fixed effects and between distributions. Report the simple correlation coefficient on the graph.

Restricted sample with a BALANCED PANEL: Two way fixed effects (TWFE) formula. Restrict the sample to the countries/individuals available with the longest duration (N=… countries over T=… periods). Compute -x(.t)+x(..), report the T numbers in a table as a function of time index and plot them as a function of time, then comment. Then compute two-way-fixed-effects x(it)-x(i.)-x(.t)+x(..) transformed variables.

TWFE Balanced panel. Compute descriptive statistics. Plot boxplots by country ordered by their variance from the smallest to the largest. TWFE Balanced panel. Present a table ordering the simple correlation coefficients of TWFE transformed dependent Y and preferred explanatory variable X by country from the largest positive to the lowest negative, with the standard error of GDPG and EDA in another column and the coefficient of simple regression: correlation coefficient \* standard error of GDPG / standard error of EDA/GDP. Comment.

UNBALANCED PANEL and TWFE transformation (remove countries with a single observation). Regress within transformed dependent Y on time dummies and collect the residuals: this is the TWFE transformation. Regress within transformed preferred explanatory variable X on time dummies and collect the residuals: this is the TWFE transformation. Alternatively, code the Wansbeek Kapstein (1989) transformation for two way fixed effects resulting in their equation 2.13 which is an extension of x(it)-x(i.)-x(.t)+x(..) obtained in the balanced panel case.

TWFE unbalanced panel: plot the distribution (Kernel DE, histogram, corresponding normal law with the same two first moments). for dependent Y and explanatory X. Compare with one-way-fixed effects, between distributions. Comparisons of the four transformed variables (Between, one-way within, two-way within, first differences). Plot boxplots of between distribution (all countries), then one-way and two-way-fixed effects and first differences distribution BY countries. (For a subset of individuals if you have a very large number of individuals >50 for example) for the dependent variable and the key explanatory variables. Comment that you find the same insights from question 5. Comment on their differences of standard errors and means for each individuals

Compute univariate descriptive statistics (min, Q1, median, Q3, max, mean, standard error) for one-way-Within, Between, two-way-fixed-effects and first differences transformed variables. Is the mean different from the median and why? How many standard errors from the mean are the MIN and MAX extremes. Report in the tables standardized MAX and MIN: (MAX-average)/standard error and (MIN-average)/standard error instead of MAX and MIN? Compare and comment the between versus one-way-within transformed bivariate correlation matrix for all variables (include a time trend 1,2,.,T) and with their lag (for time varying variables). Check poor simple correlation with the dependent variables and high correlation between explanatory variables. Comment the bivariate auto-correlation and trend-correlations (check the number of observations). In what follows, you do not need to include a deterministic time trend 1,2,.,T because the two transformations used eliminate it.

Compare and comment of the two-way-within transformed bivariate simple correlation matrix of all the variables and another bivariate simple correlation matrix with all the first differences transformed variables (in the case of first differences, include also the lag of all variables). Check poor simple correlation below 0.1 with the dependent variables and high correlation between explanatory variables (over 0.8). Show the first 30 observations for the first differences and the lag of first differences. Check that each time you change individual, you have a dot for missing observation. Comment the bivariate graphs with linear, quadratic and Lowess fit for dependent Y and key explanatory variable X on horizontal axis: Within transformed, Between transformed, First differences, two-way-within transformed.

1. Investigating bivariate heterogeneity by individuals for TWFE and FD

17 Fill in the table for heterogeneity of key correlation between individuals and slopes of the simple regression for first differences transformed variables

**Table: Heterogeneity of key correlation between individuals, sorted by correlation coefficient (numbers rounded at the 3 non-zero digit. Δ Y and Δ X are first differences transformed variables. T(i) is the number of observations used in the simple regression by individuals indexed by i.**

| Individual name (i)

| T(i)

| r( Δ Y, ΔX )

| σ ( Δ Y)

| σ ( Δ X)

| σ ( Δ Y)/ σ ( Δ X)

| β =r( Δ Y, Δ X) σ (Y)/ σ (X).

|     |
| --- | --- | --- | --- | --- | --- | --- |
|     |     |     |     |     |     |     |

Diagnosis in three groups; individuals with positive correlation larger than 0.08, individuals with negative correlation lower than -0.08, individuals with weak correlation. You may consider 5 groups for the two extremes positive versus negative. This is helpful for open question for doing regressions on subgroups.

18. Table: Heterogeneity of key correlation between individuals, sorted by correlation coefficient (numbers rounded at the 3 non-zero digit. Y and X are two way fixed effects transformed variables T(i) is the number of observations used in the simple regression by individuals indexed by i.

| Individual name (i)

| T(i)

| r(Y,X)

| σ (Y)

| σ (X)

| σ (Y)/ σ (X)

| β =r(Y,X) σ (Y)/ σ (X).

|     |
| --- | --- | --- | --- | --- | --- |
|     |     |     |     |     | 0   |

| |

Diagnosis in three groups; individuals with positive correlation larger than 0.08, individuals with negative correlation lower than -0.08, individuals with weak correlation.

19. Optional: time heterogeneity of bivariate correlation.

If T sufficiently large (for example T>20), do rolling windows estimate (for window at least equal to T=8 for 8 quarters, for example) for each individual and visualize the stability over time of estimated parameters (do it for TWFE and FD). Diagnosis: suggests a few periods for sample period dummies for each individuals.

10. Panel data estimates

In a single table, report and comment the results of estimations of Between, Within (one-way fixed effects, (fe)) and Mundlak (random effects (re) including all X(i.) as regressors), two-way fixed effects (add year dummies in fe regression) and First differences, including all explanatory variables except the ones with high near-multicollinearity after their transformation. If, for the first differences dependent variable, it remains a simple auto-correlation above 0.1, a dynamic panel estimator can be tried.

The estimators of the generalized method of moments (GMM) for panel data are only valid for short time panel T<10 and they face the issue of too many weak instruments. We suggest using its precursor, the Anderson-Hsiao (1981) estimator which allows to check the first stage of instrumental variables and to test for weak lagged instruments. Estimate an auto-regressive distributed lag (ARDL) model for dynamic panel data including the first lag of the dependent variable and the first lag of the key explanatory variable, adding the first lag of other control variables is optional:

ΔYi,t = βy ΔYi,t-1 + β1 ΔXi,t + β2 ΔXi,t-1 + Δ Controls i,t + Δ αi + Δ αt + Δ εi

For all these variables: ΔYi,t ΔYi,t-1 ΔXi,t ΔXi,t-1 Yi,t-2 Xi,t-2 report univariate statistics (mean median standard error, skewness, kurtosis, min max) and comment. Report the bivariate simple correlation coefficients matrix. The correlation between ΔYi,t-1 ΔXi,t ΔXi,t-1 and the instruments in levels: Yi,t-2 Xi,t-2 is a preliminary check for the strength of these instruments.

Do a panel data unit root test of your choice on the variables ΔYi,t and ΔXi,t and comment. With some luck, because of first differences, these variables may be stationary. Report the OLS including the lag of the first difference of the dependent ΔYi,t-1 and of other explanatory variables. Report the number of observations and the number of countries remaining in the estimation, which requires at least three consecutive observations for each country.

Report the IV estimator (IVREG) when you use the instruments in levels Yi,t-2 and Xi,t-2 . Comment how much each parameter changes when using OLS versus IV. Report the first stage regressions. Comment the R2 of each of the first stage regressions, if below 10%, it is a signal of weak instrument. You may comment statistics available in your software for weak instruments and for testing endogeneity of instruments.

Compute and plot the impulse response functions for the next four periods for 1 unit increase of X on Y:

- t=1: β1

- t=2: βy β1 + β2

- t=3: βy 2 β1 + βyβ2

- t=4: βy 3 β1 + βy 2 β2

Compute the long run coefficient of key explanatory variable on the dependent variable and comment: βLT = ( β1 + β2) / (1 - βy )

11. Optional: if one of your variable is time-invariant z(i), panel data estimators.

If one of your variable is time-invariant z(i), run a baseline Hausman Taylor estimation (pre-coded only in STATA) including all X(i.) as instruments. Comment the results. Else skip this question. If one of your variable is time-invariant z(i), run a between regression on z(i) explained by X(i.) and other time invariant variable (only with N observations). If the R2 is low, this may signal X(i.) are weak instruments poorly correlated with the variable z(i) to be instrumented. Comment. Else skip this question.

If one of your variable is time-invariant z(i), as seen above, time invariant explanatory variables cannot explain the time varying within variance of the dependent variable and the Hausman Taylor internal instruments estimator is not so practical. Therefore, a practical shortcut is to include a time invariant variable multiplied by a time varying variable (interaction term): Z(i)\*X(it). Generate such a variable Include this product AND X(it) into a one way fixed effects regression. Plot the estimated marginal effect (derivative) with respect to Z(i) as a function of X(it) for the interval [Xmin, Xmax] in the sample.

12. Your own estimations not done in the paper

Do whatever seem interesting to you in terms of original estimations (not already done by the replication of the original authors) with this database, present the table(s) in this file with comments, not only in the html output with code and output. List of references cited in the text.

Appendix:

To do list. Fill in a TO DO list for the next time you will do a study involving panel data, in particular for your master thesis (see next page). This can be done jointly by pairs of students of option 1.

An ordered to do list for your next econometric study using panel data. You may split the table into several tables for each step: data selection, variable transformations, descriptive statistics tables and visualization, estimators and endogeneity, sample splits and robustness checks… The numbers of items are unlimited.

| Tick

| Items

|     |
| --- | --- |
|     |     |
|     |     |
|     |     |
|     |     |
|     |     |

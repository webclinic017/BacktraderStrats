# Personal Remind

* short term quant, long term copy portofolio of funds
* strictly follow sell signal
* KDJ -> RSI, waiting MACD SIGNAL, finally confirm stochastic hit oversold/overbought?



# After reading thoughts on MAX MADA AUTOMATED Trading

## Chapter 6, risk, kelly criterian

### Single Strategy
**Optimizing Kelly**

Maximize compound return 

Total Gain, G
fi i th fraction
ri i th return (positive / negative)
N rounds, pN wins and (1-p)N losses
G = (1 + f1 * r1) * (1 - f2 * r2) * ... * (1 + fn * rn)
G = (1 + f)^pN + (1 - f)^(1-p)N
**Maximize log(G)**
**f = 2p - 1**

**Assuming Gaussian Returns**
maximize (avg_profit - loss)/(std_deviation of PnL), ie, E(return)/Variance(return)
Assuming getting return a or return b, (b < 0)
a = u*delta_t + theta*squre_root(delta_t)
b = u*delta_t - theta*squre_root(delta_t)

**f = u/theta^2**

### Multiple Strategies

SUM(wi*Xi)
Xi are the PnL distributions of each strategy
wi weighted, fractions of each strategy
Risk is Var(SUM(wi * Xi)) = SUM(wi^2 * Var(Xi)) + SUM((wi * wj) * Covariance(Xi, Xj))
Covariance(Xi, Xj) = SD(Xi) * SD(Xj) * Correlation(Xi, Xj)
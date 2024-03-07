import time
import pandas as pd
import scipy
import os
from datetime import datetime
import numpy as np
from scipy.linalg import cholesky
from scipy.stats import norm
from scipy.special import laguerre
import matplotlib.pyplot as plt

class BSDEOptionPricingEuropean:
    def __init__(self, S0, K, r, sigma, T, N, M, lower = 0.025, samples = 100,
                 option_payoff="call", degree = 3, mu = 0.05, picard = 3):
        if not isinstance(S0, (int, float)) or S0 <= 0:
            raise ValueError('S0 must be positive.')
        if not isinstance(K, (int, float)) or K <= 0:
            raise ValueError('K must be positive.')
        if not isinstance(T, (int, float)) or T <= 0:
            raise ValueError('T must be positive.')
        if not isinstance(r, (int, float)):
            raise ValueError('r must be integer or float.')
        if not isinstance(sigma, (int, float)) or sigma <= 0:
            raise ValueError('sigma must be positive.')
        if not isinstance(N, int) or N <= 0:
            raise ValueError('N must be a positive integer.')
        if not isinstance(M, int) or M <= 0:
            raise ValueError('M must be a positive integer.')
        if not isinstance(degree, int) or degree < 0:
            raise ValueError('degree must be a non-negative integer.')
        if not isinstance(lower, float):
            raise ValueError('Lower confidence number msut be a float!')

        self.S0 = S0
        self.K = K
        self.T = T
        self.r = r
        self.mu = mu
        self.sigma = sigma
        self.N = N
        self.M = M
        self.option_payoff = self._get_opt_payoff(option_payoff)
        self.degree = degree
        self.dt = T / N
        self.samples = samples
        self.lower = lower
        self.lamb = (mu - r)/(sigma)
        self.picard = picard

    def _get_opt_payoff(self, opt_payoff):
        """ Retrieves option payoff """
        if not isinstance(opt_payoff, str):
            raise TypeError('Option type should be a string!')
        if opt_payoff.lower() == 'call':
            return 'call'
        elif opt_payoff.lower() == 'put':
            return 'put'
        else:
            raise TypeError('Invalid option type! It should be call or put')

    def _payoff_func(self, S):
        """ Payoff function depending on the options payoff type """
        if self.option_payoff == "call":
            return np.maximum(S - self.K, 0) 
        elif self.option_payoff == "put":
            return np.maximum(self.K - S, 0)
        else:
            raise ValueError(f"Invalid option type: {self.option_type}. Supported types are 'call' and 'put'.")

    def _generate_regression(self, S):
        """ Generates Laguerre polynomials up to degree self.degree """
        if self.degree > 20 or self.degree < 1:
            raise ValueError(f"Invalid degree on Polynomial basis, you chose: {self.degree}, choose between 1 and 10")
        
        S_expanded = np.expand_dims(S, axis=-1)   
        basis_polynomials = np.array([np.polynomial.laguerre.Laguerre.basis(deg)(S_expanded) for deg in range(self.degree + 1)])
        Mk = np.transpose(basis_polynomials, (1, 2, 0)).reshape(S.shape[0], self.degree + 1)
        return Mk

    def _generate_stock_paths(self):
        """Simulate Geometric Brownian Motion paths."""
        dt = self.T / self.N
        dW = np.random.normal(0, np.sqrt(dt), (self.M, self.N + 1))
        log_S = np.cumsum((self.mu - 0.5 * self.sigma**2) * dt + self.sigma * dW, axis=1)
        S = self.S0 * np.exp(np.hstack([np.zeros((self.M, 1)), log_S]))
        return S, dW

    def _bsde_solver(self):
        """ Solves the BSDE equation for an european option using Cholesky Decomposition"""
        Y0_samples = np.zeros(self.samples)

        for k in range(self.samples):
            S, dW = self._generate_stock_paths()
            Y = np.zeros((self.M, self.N + 1))

            Y[:, -1] = self._payoff_func(S[:, -1])

            for i in range(self.N, 0, -1):
                X = self._generate_regression(S[:, i])
                A = X.T @ X
                alpha = np.linalg.lstsq(A, X.T @ Y[:, i], rcond=None)[0]
                continuation_value = X @ alpha
                Y[:, i-1] = continuation_value * np.exp(-self.r * self.dt)

            Y0_samples[k] = np.mean(Y[:, 0])

        return Y0_samples, 0

    def _confidence_interval(self, sample):
        """ Calculates the confidence interval with lower limit self.lower """
        mean_sample = np.mean(sample)
        std_sample = np.std(sample)
        upper = mean_sample + norm.ppf(1-self.lower/2) * std_sample/np.sqrt(self.M)
        lower = mean_sample - norm.ppf(1-self.lower/2) * std_sample/np.sqrt(self.M)
        CI = [round(lower,4), round(upper,4)]
        return mean_sample, std_sample, CI


    def plot_and_show_table_by_degree(self, degrees, option_type='call'):
        prices = []
        errors = []
        rows = []
        
        for degree in degrees:
            self.degree = degree  
            Y0_array, _ = self._bsde_solver()
            est_Y0, std_Y0, CI_Y = self._confidence_interval(Y0_array)
            prices.append(est_Y0)
            errors.append(std_Y0)
            rows.append([degree, est_Y0, std_Y0, CI_Y[0], CI_Y[1]])
        
        plt.errorbar(degrees, prices, yerr=errors, fmt='-o', capsize=5, capthick=2, ecolor='red', label='Option Price')
        plt.xlabel('Degree of Laguerre Polynomials')
        plt.ylabel('Option Price')
        plt.title('Option Price vs. Degree of Laguerre Polynomials')
        plt.legend()
        plt.grid(True)
        plt.show()
        
        df = pd.DataFrame(rows, columns=['Degree', 'Estimated Price', 'Std. Deviation', 'CI Lower Bound', 'CI Upper Bound'])
        print(df)

    def run(self):
        """ Method called to run the program and solve the BSDE """
        start_timer = time.time()
        Y0_array, Z0_array = self._bsde_solver()
        finished_time = time.time() - start_timer
        est_Y0, std_Y0, CI_Y = self._confidence_interval(Y0_array)
        est_Z0, std_Z0, CI_Z = self._confidence_interval(Z0_array)
        print(f"\nBSDE solved in: {finished_time:.2f} seconds"
                f"\nEstimated option price: {est_Y0:.4f}"
                f"\nWith standard deviation: {std_Y0:.4f}"
                f"\nConfidence interval: {CI_Y}"
                f"\nEstimated hedge strategy: {est_Z0:.4f}"
                f"\nWith standard deviation: {std_Z0:.4f}"
                f"\nConfidence interval: {CI_Z}")

class BSDEOptionPricingAmerican(BSDEOptionPricingEuropean):

    def _bsde_solver(self):
        """ Solves the BSDE equation for an european option using Cholesky Decomposition"""
        Y0_samples = np.zeros(self.samples)

        for k in range(self.samples):
            S, dW = self._generate_stock_paths()
            Y = np.zeros((self.M, self.N + 1))

            Y[:, -1] = self._payoff_func(S[:, -1])

            for i in range(self.N, 0, -1):
                X = self._generate_regression(S[:, i])
                A = X.T @ X
                alpha = np.linalg.lstsq(A, X.T @ Y[:, i], rcond=None)[0]
                continuation_value = X @ alpha
                exercise_value = self._payoff_func(S[:, i])
                Y[:, i-1] = np.maximum(continuation_value * np.exp(-self.r * self.dt), exercise_value)
                

            Y0_samples[k] = np.mean(Y[:, 0])

        return Y0_samples, 0


class BSDEOptionPricingEuropeanSpread(BSDEOptionPricingEuropean):
    def __init__(self, S0, K, r, sigma, T, N, M, lower, samples, option_payoff, degree, mu, K2, R):
        super().__init__(S0, K, r, sigma, T, N, M, lower, samples, option_payoff, degree, mu)
        self.K2 = 105 if K2 is None else K2 
        self.R = 0.06 if R is None else R 

    def _payoff_func(self, S):
        if self.option_payoff == "call":
            return np.maximum(S - self.K, 0) - 2*np.maximum(S - self.K2, 0) 
        else:
            raise ValueError(f"Invalid option type: {self.option_type}. Supported types are 'call' and 'put'.")

    def _bsde_solver(self):
        """ Solves the BSDE equation for an european option using Cholesky Decomposition"""
        Y0_samples = np.zeros(self.samples)

        for k in range(self.samples):
            S, dW = self._generate_stock_paths()
            Y = np.zeros((self.M, self.N + 1))
            Z = np.zeros((self.M, self.N + 1))

            Y[:, -1] = self._payoff_func(S[:, -1])

            for i in range(self.N, 0, -1):
                X = self._generate_regression(S[:, i])
                A = X.T @ X
                alpha_y = np.linalg.lstsq(A, X.T @ Y[:, i], rcond=None)[0]
                alpha_z = np.linalg.lstsq(A, X.T @ (Y[:, i] * dW[:, i]), rcond=None)[0]
                E = X @ alpha_y
                Z[:, i] = X @ alpha_z 
                for _ in range(self.picard):
                    Y[:, i-1] = E + (-self.r*Y[:, i] + self.lamb*Z[:, i] - (self.R - self.r)*np.min(Y[:, i] -Z[:, i]/self.sigma, 0))*self.dt

            Y0_samples[k] = np.mean(Y[:, 0])

        return Y0_samples, 0


class BSDEOptionPricingAmericanSpread(BSDEOptionPricingAmerican):
    def __init__(self, S0, K, r, sigma, T, N, M, lower, samples, option_payoff, degree, mu, K2, R):
        super().__init__(S0, K, r, sigma, T, N, M, lower, samples, option_payoff, degree, mu)
        self.K2 = 105 if K2 is None else K2 
        self.R = 0.06 if R is None else R 

    def _payoff_func(self, S):
        if self.option_payoff == "call":
            return np.maximum(S - self.K, 0) - np.maximum(S - self.K2, 0) 
        else:
            raise ValueError(f"Invalid option type: {self.option_type}. Supported types are 'call'.")

    def _bsde_solver(self):
        """ Solves the BSDE equation for an european option using Cholesky Decomposition"""
        Y0_samples = np.zeros(self.samples)
        Z0_samples = np.zeros(self.samples)

        for k in range(self.samples):
            S, dW = self._generate_stock_paths()
            Y = np.zeros((self.M, self.N + 1))
            Z = np.zeros((self.M, self.N + 1))

            Y[:, -1] = self._payoff_func(S[:, -1])

            for i in range(self.N, 0, -1):
                X = self._generate_regression(S[:, i])
                A = X.T @ X
                alpha_y = np.linalg.lstsq(A, X.T @ Y[:, i], rcond=None)[0]
                alpha_z = np.linalg.lstsq(A, X.T @ (Y[:, i] * dW[:, i]), rcond=None)[0]
                E = X @ alpha_y
                Z[:, i] = X @ alpha_z 
                exercise_value = self._payoff_func(S[:, i])
                for _ in range(self.picard):
                    Y[:, i-1] = E + (-self.r*Y[:, i] + self.lamb*Z[:, i] - (self.R - self.r)*np.min(Y[:, i] -Z[:, i]/self.sigma, 0))*self.dt
                Y[:, i-1] = np.maximum(exercise_value, Y[:, i-1])
                
            Y0_samples[k] = np.mean(Y[:, 0])
            Z0_samples[k] = np.mean(Z[:, 1])


        return Y0_samples, 0

# ---------------------------------------------------------
# Project: ATLAS OS v18.5 - MACHINE (IMAGO)
# Author: Iggy-Atlas
# Year: 2026
# License: All Rights Reserved / Proprietary
# Description: Personal AI Operating System for Termux.
# Intellectual Property of Iggy-Atlas.
# ---------------------------------------------------------


import sympy as sp

class ScienceCore:
    def solve_equation(self, eq_str):
        try:
            x = sp.symbols('x')
            # Zamjena za potencije i čišćenje
            eq_str = eq_str.replace("^", "**")
            if '=' in eq_str:
                parts = eq_str.split('=')
                lhs = sp.parse_expr(parts[0].strip())
                rhs = sp.parse_expr(parts[1].strip())
                eq = sp.Eq(lhs, rhs)
                sol = sp.solve(eq, x)
            else:
                expr = sp.parse_expr(eq_str)
                sol = sp.solve(expr, x)
            return f"Rješenje: {sol}"
        except Exception as e:
            return f"Matematička pogreška: {str(e)}"

    def simple_calc(self, expression):
        try:
            # Precizan izračun bez numpy-ja
            result = sp.sympify(expression).evalf()
            return f"Rezultat: {result}"
        except Exception as e:
            return f"Pogreška: {str(e)}"

import marimo

__generated_with = "0.10.14"
app = marimo.App(width="medium")


@app.cell
def _():
    return


@app.cell
def _():
    import pyomo.environ as pyo
    from pyomo.opt import SolverFactory
    import pandas as pd
    return SolverFactory, pd, pyo


@app.cell
def _(pd):
    # Load data from Excel
    file_path = "Data.xlsx"
    data = pd.ExcelFile(file_path)
    return data, file_path


@app.cell
def _(file_path, pd):
    # Read specific sheets
    daily_production = pd.read_excel(file_path, sheet_name='forcast production')  # Daily expected production in MW
    daily_prices = pd.read_excel(file_path, sheet_name='price of electricity')  # Daily energy prices in €/MW
    daily_maintenance_coeff = pd.read_excel(file_path, sheet_name='maintenance coefficient')  # Coefficient for maintenance cost
    return daily_maintenance_coeff, daily_prices, daily_production


@app.cell
def _(daily_maintenance_coeff, daily_prices, daily_production, pyo):
    def get_answer(extra_constraint):
        # Model definition
        model = pyo.ConcreteModel()

        n_days = len(daily_production)  # Number of days in the planning horizon

        # Sets and Parameters
        model.DAYS = pyo.RangeSet(1, n_days)
        model.Production = pyo.Param(model.DAYS, initialize=daily_production.set_index('period')['forecastp'].to_dict())
        model.Prices = pyo.Param(model.DAYS, initialize=daily_prices.set_index('period')['price'].to_dict())
        model.MaintenanceCoeff = pyo.Param(model.DAYS, initialize=daily_maintenance_coeff.set_index('period')['coeff'].to_dict())

        # Engineer availability (hardcoded for periods 300-365)
        if extra_constraint:
            engineer_availability = {d: 1 if 300 <= d <= 365 else 0 for d in range(1, n_days + 1)}
        else:
            engineer_availability = {1 for d in range(1, n_days + 1)}
        model.Availability = pyo.Param(model.DAYS, initialize=engineer_availability)

        # Binary indicator for the strategy
        model.UseSplit = pyo.Var(domain=pyo.Binary)

        # Maintenance start variables
        model.Start5 = pyo.Var(model.DAYS, domain=pyo.Binary)
        model.Start3 = pyo.Var(model.DAYS, domain=pyo.Binary)
        model.Start2 = pyo.Var(model.DAYS, domain=pyo.Binary)

        # Maintenance (is the plant down on day d?)
        model.Maintenance = pyo.Var(model.DAYS, domain=pyo.Binary)

        ##################################################################
        # Maintenance availability
        ##################################################################
        for d in model.DAYS:
            if not model.Availability[d]:
                model.Start5[d].fix(0)
                model.Start3[d].fix(0)
                model.Start2[d].fix(0)

        ##################################################################
        # Exactly one 5-day OR exactly one 3-day plus exactly one 2-day
        ##################################################################
        @model.Constraint()
        def OneStrategy_5DayOR3and2(m):
            return sum(m.Start5[d] for d in m.DAYS) == 1 - m.UseSplit

        @model.Constraint()
        def OneStrategy_3day(m):
            return sum(m.Start3[d] for d in m.DAYS) == m.UseSplit

        @model.Constraint()
        def OneStrategy_2day(m):
            return sum(m.Start2[d] for d in m.DAYS) == m.UseSplit

        ##################################################################
        # Link Maintenance[d] with the chosen start day
        # If day d is in a 5-day window or 3-day or 2-day window
        ##################################################################
        @model.Constraint(model.DAYS)
        def MaintenanceLink(m, d):
            # 5-day window coverage
            days_5 = []
            for k in range(max(1, d-4), d+1):  # k in [d-4, d]
                days_5.append(m.Start5[k])
            # 3-day window coverage
            days_3 = []
            for k in range(max(1, d-2), d+1):  # k in [d-2, d]
                days_3.append(m.Start3[k])
            # 2-day window coverage
            days_2 = []
            for k in range(max(1, d-1), d+1):  # k in [d-1, d]
                days_2.append(m.Start2[k])

            return m.Maintenance[d] == sum(days_5) + sum(days_3) + sum(days_2)

        ##################################################################
        # Objective: Max revenue (Production * Price) on non-maintenance days
        ##################################################################
        model.Revenue = pyo.Objective(
            expr=sum(20 * model.Production[d] * model.Prices[d] * (1 - model.Maintenance[d]) 
                     for d in model.DAYS),
            sense=pyo.maximize
        )

        ##################################################################
        # Solve
        ##################################################################
        solver = pyo.SolverFactory('glpk')
        results = solver.solve(model, tee=True)

        return model, results
    return (get_answer,)


@app.cell
def _(pyo):
    def print_solution(model, results):
        # Check solution
        if (results.solver.status == pyo.SolverStatus.ok) and \
           (results.solver.termination_condition == pyo.TerminationCondition.optimal):
            print("Optimal solution found.")
            # Inspect which strategy was chosen
            if pyo.value(model.UseSplit) == 0:
                print("Chosen strategy: 5-day maintenance.")
                for da in model.DAYS:
                    if pyo.value(model.Start5[da]) > 0.5:
                        print(f"5-day window starts on day {da}")
            else:
                print("Chosen strategy: 3-day + 2-day maintenance.")
                for da in model.DAYS:
                    if pyo.value(model.Start3[da]) > 0.5:
                        print(f"3-day window starts on day {da}")
                    if pyo.value(model.Start2[da]) > 0.5:
                        print(f"2-day window starts on day {da}")

            print("Total Revenue:", round(pyo.value(model.Revenue), 2))
        else:
            print("No feasible solution or solver error.")
    return (print_solution,)


@app.cell
def _(get_answer, print_solution):
    for extra in [False, True]:
        model, results = get_answer(extra)
        print("\n" + '*'*30)
        print(f"Extra Constraint: {extra}")
        print_solution(model, results)
        print('*'*30 + "\n")
    return extra, model, results


if __name__ == "__main__":
    app.run()

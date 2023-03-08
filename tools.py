from datetime import timedelta, date

import pandas as pd

# Read the input csv file
df = pd.read_csv('work_hours.csv')

df['Duration'] = pd.to_datetime(df['Check Out']) - pd.to_datetime(df['Check In'])

# Convert the 'Date' column to datetime type
df['Date'] = pd.to_datetime(df['Date'])

# Create a new column for the check-in/check-out number (0, 1, etc.)
df['Check In/Out'] = df.groupby(df['Date']).cumcount()

# Pivot the dataframe to create separate columns for each check-in and check-out time
df_pivoted = df.pivot(index='Date', columns='Check In/Out', values=['Check In', 'Check Out'])

today = date.today()

df_duration = df[['Date', 'Duration']]
df_duration = df_duration[df_duration['Date'].dt.date < today]
duration = df_duration['Duration'].groupby(df_duration['Date']).aggregate(sum)

day_work_hours = timedelta(hours=8)
extra_duration = duration >= day_work_hours
missing_duration = duration < day_work_hours
extra_time = duration[extra_duration] - day_work_hours
missing_time = - duration[missing_duration] + day_work_hours

net_time = (duration - day_work_hours).sum()
print(net_time)

# Flatten the column names
column_names = ['{}-{}'.format(col[1], col[0]) for col in df_pivoted.columns]
df_pivoted.columns = ['{}-{}'.format(col[1], col[0]) for col in df_pivoted.columns]
column_names = sorted(column_names)

df_pivoted = df_pivoted[column_names]
idx = pd.date_range(min(df_pivoted.index), max(df_pivoted.index))

df_pivoted = df_pivoted.reindex(idx).fillna('')

df_formatted = pd.DataFrame(
    [
        pd.to_datetime(df_pivoted[col]).dt.strftime("%H:%M")
        for col in column_names
    ]
).transpose()

# Reset the index and rename the columns
df_formatted = df_formatted.reset_index().rename(columns={'index': 'Date'})

# Write the output csv file
df_formatted.to_csv('work_time_pivoted.csv', index=False)
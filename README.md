# blackmarket-bigquery

## Summary
This project simulates a black-market marketplace and builds a data pipeline to detect scam vendors using synthetic transaction data.

## Overview
<img width="435" height="281" alt="architecture" src="https://github.com/user-attachments/assets/e765eb83-f4be-4eec-bbce-87ccb33daefc" />

### Table of Contents

1. [Data Generator](#data-generator)
2. [OLTP data to BigQuery](#oltp-data-to-bigquery)
3. [Data transformations](#data-transformations)
4. [Data validation](#data-validation)
5. [Training data gathering](#training-data-gathering)
6. [Machine Learning](#machine-learning)

### Data Generator

Generates synthetic data based on a few basic logical business rules.

- [csvgenerator.py](data-generator/csvgenerator.py)
- [table_info.txt](data-generator/table_info.txt)
- [oltp_schema.txt](data-generator/_schemas/oltp_schema.txt)
- [olap_schema.txt](data-generator/_schemas/olap_schema.txt)

### OLTP data to BigQuery

- [csvuploader.py](data-generator/csvuploader.py)

### Data transformations
- [transformation scripts](definitions)

### Data validation
- [assertions](data-generator/assertion)

### Training data gathering
- [ml definitions](definitions/ml)

### Machine Learning
- [ml scripts](ml)

## train.py
use cache:              python train.py
re-fetches from BQ:     python train.py --refresh

## predict.py
### basic
python predict.py --input new_vendors.csv

### custom output path
python predict.py --input new_vendors.csv --output ./ml/results.csv

### lower threshold to catch more scammers (more false positives but higher recall)
python predict.py --input new_vendors.csv --threshold 0.3

## test_generator.py
### generate 200 vendors with label (for checking model accuracy)
python generate_test.py

### generate without label (to feed into predict.py)
python generate_test.py --no-label --output ./ml/new_vendors.csv

### then run predictions on it
python predict.py --input ./ml/new_vendors.csv
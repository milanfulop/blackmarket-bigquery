"""
CSV to BigQuery Bulk Uploader
Upload multiple CSV files to BigQuery raw data layer
"""

from google.cloud import bigquery
from pathlib import Path
import os
from typing import Optional
import time

class CSVToBigQueryUploader:
    def __init__(self, project_id: str, dataset_id: str = "raw_oltp"):
        """
        Initialize the uploader
        
        Args:
            project_id: Your GCP project ID
            dataset_id: BigQuery dataset name (default: raw_oltp)
        """
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.client = bigquery.Client(project=project_id)
        
        # Create dataset if it doesn't exist
        self._create_dataset_if_not_exists()
    
    def _create_dataset_if_not_exists(self):
        """Create the dataset if it doesn't already exist"""
        dataset_ref = f"{self.project_id}.{self.dataset_id}"
        
        try:
            self.client.get_dataset(dataset_ref)
            print(f"✓ Dataset {self.dataset_id} already exists")
        except Exception:
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = "US"  # Change if you need a different region
            self.client.create_dataset(dataset)
            print(f"✓ Created dataset {self.dataset_id}")
    
    def upload_csv(
        self, 
        csv_path: str, 
        table_name: Optional[str] = None,
        write_disposition: str = "WRITE_TRUNCATE"
    ):
        """
        Upload a single CSV file to BigQuery
        
        Args:
            csv_path: Path to CSV file
            table_name: Optional custom table name (defaults to filename)
            write_disposition: 
                - WRITE_TRUNCATE: Replace table (default)
                - WRITE_APPEND: Add to existing table
                - WRITE_EMPTY: Only write if table is empty
        """
        csv_file = Path(csv_path)
        
        if not csv_file.exists():
            print(f"✗ File not found: {csv_path}")
            return False
        
        # Use filename as table name if not provided
        if table_name is None:
            table_name = csv_file.stem.lower().replace(" ", "_").replace("-", "_")
        
        table_ref = f"{self.project_id}.{self.dataset_id}.{table_name}"
        
        # Configure the load job
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,  # Skip header row
            autodetect=True,  # Auto-detect schema from CSV
            write_disposition=write_disposition,
            # Optional: Specify encoding if you have special characters
            # encoding='UTF-8',
        )
        
        print(f"⏳ Uploading {csv_file.name} → {table_name}...")
        
        try:
            with open(csv_file, "rb") as source_file:
                load_job = self.client.load_table_from_file(
                    source_file,
                    table_ref,
                    job_config=job_config
                )
            
            # Wait for the job to complete
            load_job.result()
            
            # Get table info
            table = self.client.get_table(table_ref)
            
            print(f"✓ {table_name}: {table.num_rows:,} rows, {len(table.schema)} columns")
            return True
            
        except Exception as e:
            print(f"✗ Error uploading {csv_file.name}: {str(e)}")
            return False
    
    def upload_directory(
        self, 
        directory_path: str,
        file_pattern: str = "*.csv",
        write_disposition: str = "WRITE_TRUNCATE"
    ):
        """
        Upload all CSV files from a directory
        
        Args:
            directory_path: Path to directory containing CSV files
            file_pattern: Pattern to match files (default: *.csv)
            write_disposition: How to write data (TRUNCATE/APPEND/EMPTY)
        """
        directory = Path(directory_path)
        
        if not directory.exists():
            print(f"✗ Directory not found: {directory_path}")
            return
        
        csv_files = list(directory.glob(file_pattern))
        
        if not csv_files:
            print(f"✗ No CSV files found in {directory_path}")
            return
        
        print(f"\n{'='*60}")
        print(f"Found {len(csv_files)} CSV file(s) to upload")
        print(f"Target: {self.project_id}.{self.dataset_id}")
        print(f"{'='*60}\n")
        
        successful = 0
        failed = 0
        start_time = time.time()
        
        for csv_file in csv_files:
            if self.upload_csv(csv_file, write_disposition=write_disposition):
                successful += 1
            else:
                failed += 1
            print()  # Empty line between uploads
        
        elapsed_time = time.time() - start_time
        
        print(f"{'='*60}")
        print(f"Upload Complete!")
        print(f"✓ Successful: {successful}")
        if failed > 0:
            print(f"✗ Failed: {failed}")
        print(f"⏱ Time: {elapsed_time:.2f} seconds")
        print(f"{'='*60}\n")
    
    def list_tables(self):
        """List all tables in the dataset"""
        tables = self.client.list_tables(f"{self.project_id}.{self.dataset_id}")
        
        print(f"\nTables in {self.dataset_id}:")
        print(f"{'-'*60}")
        
        for table in tables:
            full_table = self.client.get_table(table)
            print(f"{table.table_id}: {full_table.num_rows:,} rows")


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def main():
    """Main function - modify this for your use case"""
    
    # CONFIGURATION - CHANGE THESE VALUES
    PROJECT_ID = "blackmarket-488113"  # Your GCP project ID
    DATASET_ID = "raw_oltp"  # Where to store raw data
    CSV_DIRECTORY = "./light"  # Folder containing your CSV files
    
    # Initialize uploader
    uploader = CSVToBigQueryUploader(
        project_id=PROJECT_ID,
        dataset_id=DATASET_ID
    )
    
    # OPTION 1: Upload all CSVs from a directory
    uploader.upload_directory(CSV_DIRECTORY)
    
    # OPTION 2: Upload specific files individually
    # uploader.upload_csv("./data/customers.csv")
    # uploader.upload_csv("./data/orders.csv")
    # uploader.upload_csv("./data/products.csv", table_name="dim_products")
    
    # OPTION 3: Append data instead of replacing
    # uploader.upload_directory(CSV_DIRECTORY, write_disposition="WRITE_APPEND")
    
    # List uploaded tables
    uploader.list_tables()


if __name__ == "__main__":
    main()
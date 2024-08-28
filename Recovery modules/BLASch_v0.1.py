# Description: This script is designed to filter chimeric sequences from a set of FASTA files based on BLAST results.

# Import necessary libraries
import os
import logging
import shutil
import subprocess
import multiprocessing as mp
from Bio import SeqIO

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define directories and paths
input_dir = '/home/ali/Documents/pipe/test/input'
blast_output_dir = '/home/ali/Documents/pipe/test/blast_output'
output_dir_begin = '/home/ali/Documents/pipe/test/begin'
output_dir_end = '/home/ali/Documents/pipe/test/end'
rescued_dir = '/home/ali/Documents/pipe/test/rescued_reads'
db = '/home/ali/Documents/pipe/test/database/EUK'
header = "qseqid stitle qlen slen qstart qend sstart send evalue length nident mismatch gapopen gaps sstrand qcovs pident"

# Step 1: Clean and create necessary directories
def clean_directory(directory):
    if os.path.exists(directory):
        if os.listdir(directory):  # Check if directory is not empty
            logging.info(f"Directory {directory} exists and is not empty. Deleting old results...")
            shutil.rmtree(directory)  # Delete the directory and its contents
        else:
            logging.info(f"Directory {directory} exists but is empty.")
    else:
        logging.info(f"Directory {directory} does not exist. Creating it...")
    os.makedirs(directory, exist_ok=True)  # Recreate the directory

# Clean and create directories
clean_directory(output_dir_begin)
clean_directory(output_dir_end)
clean_directory(rescued_dir)

# Step 2: Check if the FASTA and BLAST directories contain the same files
def check_file_pairs(fasta_dir, blast_dir):
    fasta_files = set(os.path.splitext(f)[0] for f in os.listdir(fasta_dir) if f.endswith(".fasta"))
    blast_files = set(os.path.splitext(f)[0] for f in os.listdir(blast_dir) if f.endswith(".txt"))

    missing_blasts = fasta_files - blast_files
    missing_fastas = blast_files - fasta_files

    if missing_blasts:
        logging.error(f"Missing BLAST results for the following FASTA files: {', '.join(missing_blasts)}")
    
    if missing_fastas:
        logging.error(f"Missing FASTA files for the following BLAST results: {', '.join(missing_fastas)}")
    
    # Return only the files that have pairs
    valid_files = fasta_files & blast_files
    return valid_files

# Step 3: Filter sequences based on BLAST results with error handling
def filter_sequences(blast_file_path, qcov_threshold=99, pident_threshold=99):
    flagged_sequences = []
    nonchimeric_sequences = []
    
    with open(blast_file_path, 'r') as file:
        lines = file.readlines()
        if not lines:
            logging.warning(f"No BLAST hits found in file: {blast_file_path}")
            return flagged_sequences, nonchimeric_sequences

        for line in lines:
            # Skip header lines
            if line.startswith("qseqid"):
                continue
            
            parts = line.strip().split('+')
            if len(parts) < 17:
                logging.warning(f"Skipping line due to unexpected format (less than 17 fields): {line.strip()}")
                continue

            qseqid = parts[0]
            try:
                qcov = float(parts[15])
                pident = float(parts[16])
            except ValueError as e:
                logging.error(f"Error parsing qcov or pident in line: {line.strip()} - {e}")
                continue
            
            if qcov >= qcov_threshold and pident >= pident_threshold:
                nonchimeric_sequences.append(qseqid)
            else:
                flagged_sequences.append(qseqid)
    
    return flagged_sequences, nonchimeric_sequences

# Step 4: Save nonchimeric sequences to the "rescued_reads" folder without line breaks
def save_nonchimeric_sequences(input_file, nonchimeric_sequences, output_dir):
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    nonchimeric_file = os.path.join(output_dir, f"{base_name}_rescued.fasta")

    with open(input_file) as handle:
        records = [record for record in SeqIO.parse(handle, "fasta") if record.id in nonchimeric_sequences]

    with open(nonchimeric_file, 'w') as output_handle:
        for record in records:
            output_handle.write(f">{record.id}\n{str(record.seq)}\n")

# Step 5: Trim sequences and save to separate files
def trim_sequences(input_file, output_dir_begin, output_dir_end, filtered_sequences):
    base_name = os.path.splitext(os.path.basename(input_file))[0]

    with open(input_file) as handle:
        records = [record for record in SeqIO.parse(handle, "fasta") if record.id in filtered_sequences]

    trimmed_begin = []
    trimmed_end = []

    for record in records:
        # Trim the first 100 bases
        if len(record.seq) >= 100:
            trimmed_begin.append(record[:100])
        else:
            # If the sequence is shorter than 100 bases, take the full sequence
            trimmed_begin.append(record[:])

        # Trim the last 100 bases
        if len(record.seq) >= 100:
            trimmed_end.append(record[-100:])
        else:
            # If the sequence is shorter than 100 bases, take the full sequence
            trimmed_end.append(record[:])

    # Write sequences without line breaks
    with open(os.path.join(output_dir_begin, f"{base_name}_begin.fasta"), "w") as output_handle:
        for record in trimmed_begin:
            output_handle.write(f">{record.id}\n{str(record.seq)}\n")

    with open(os.path.join(output_dir_end, f"{base_name}_end.fasta"), "w") as output_handle:
        for record in trimmed_end:
            output_handle.write(f">{record.id}\n{str(record.seq)}\n")

# Step 6: Run BLAST on trimmed sequences
def run_blast(fasta_file, db, header):
    output_dir = os.path.dirname(fasta_file)
    base_name = os.path.splitext(os.path.basename(fasta_file))[0]
    total_seqs = sum(1 for _ in SeqIO.parse(fasta_file, "fasta"))

    num_chunks = 5 if total_seqs <= 500 else 10
    seq_per_chunk = total_seqs // num_chunks

    # Split the FASTA file into chunks
    with open(fasta_file) as f:
        records = list(SeqIO.parse(f, "fasta"))
        for i in range(num_chunks):
            chunk_records = records[i * seq_per_chunk:(i + 1) * seq_per_chunk]
            chunk_file = f"{output_dir}/{base_name}_chunk_{i + 1}.fasta"
            SeqIO.write(chunk_records, chunk_file, "fasta")
    
    # Run BLAST for each chunk
    for i in range(num_chunks):
        chunk_file = f"{output_dir}/{base_name}_chunk_{i + 1}.fasta"
        blast_output = f"{chunk_file}_blast_results.txt"
        
        subprocess.run([
            'blastn',
            '-query', chunk_file,
            '-db', db,
            '-word_size', '7',
            '-task', 'blastn',
            '-num_threads', '8',
            '-outfmt', f'6 delim=+ {header}',
            '-evalue', '0.001',
            '-strand', 'both',
            '-max_target_seqs', '10',
            '-max_hsps', '1',
            '-out', blast_output
        ])
        
        # Add header to the output file
        subprocess.run(['sed', '-i', f'1i{header}', blast_output])
        os.remove(chunk_file)
    
    # Combine and deduplicate the results
    combined_output = f"{output_dir}/combined_blast_top10hit.txt"
    with open(combined_output, 'w') as outfile:
        for i in range(num_chunks):
            chunk_file = f"{output_dir}/{base_name}_chunk_{i + 1}.fasta_blast_results.txt"
            with open(chunk_file) as infile:
                outfile.write(infile.read())
            os.remove(chunk_file)
    
    dedup_output = f"{output_dir}/{base_name}.txt"
    with open(combined_output) as infile, open(dedup_output, 'w') as outfile:
        seen = set()
        for line in infile:
            if line.split('+')[0] not in seen:
                seen.add(line.split('+')[0])
                outfile.write(line)
    os.remove(combined_output)

# Step 7: Check database identifiers match between begin and end BLAST results
def check_database_identifier(begin_blast_line, end_blast_line):
    begin_parts = begin_blast_line.split('+')
    end_parts = end_blast_line.split('+')
    
    # Extract database identifiers
    begin_db_id = begin_parts[1]
    end_db_id = end_parts[1]
    
    # Check if they match
    return begin_db_id == end_db_id

# Step 8: Criteria function to determine if a sequence is non-chimeric
def check_criteria(qlen, slen, qstart, qend, sstart, send, qcov, pident):
    if qcov >= 95 and pident >= 95:
        return True  # Non-chimeric
    else:
        return False  # Chimeric

# Step 9: Parse the BLAST output file for a specific sequence
def parse_blast_file(blast_file_path, qseqid):
    with open(blast_file_path, 'r') as file:
        lines = file.readlines()
        if not lines:
            logging.warning(f"No BLAST hits found for {qseqid} in file: {blast_file_path}")
            return None  # No BLAST hits, consider as chimeric
        
        for line in lines:
            if line.startswith("qseqid"):
                continue
            
            if line.startswith(qseqid):
                parts = line.strip().split('+')
                if len(parts) < 17:
                    logging.warning(f"Skipping line due to unexpected format (less than 17 fields): {line.strip()}")
                    continue
                
                qlen = int(parts[2])
                slen = int(parts[3])
                qstart = int(parts[4])
                qend = int(parts[5])
                sstart = int(parts[6])
                send = int(parts[7])
                evalue = float(parts[8])
                qcov = float(parts[15])
                pident = float(parts[16])

                return qlen, slen, qstart, qend, sstart, send, qcov, pident

    return None  # Return None if no valid data is found or no BLAST hits

# Step 10: Process each qseqid and determine chimeric/non-chimeric status
def process_qseqid(qseqid):
    base_name = qseqid.split('.')[0]
    blast_file_begin = os.path.join(output_dir_begin, f"{base_name}_begin.txt")
    blast_file_end = os.path.join(output_dir_end, f"{base_name}_end.txt")

    begin_data = parse_blast_file(blast_file_begin, qseqid)
    end_data = parse_blast_file(blast_file_end, qseqid)

    if not begin_data or not end_data:
        return None  # Skip this sequence if either begin or end data is missing

    begin_line = next((line for line in open(blast_file_begin) if line.startswith(qseqid)), None)
    end_line = next((line for line in open(blast_file_end) if line.startswith(qseqid)), None)
    
    if begin_line and end_line and not check_database_identifier(begin_line, end_line):
        return None  # Skip this sequence if database identifiers do not match

    non_chimeric_b = check_criteria(*begin_data)
    non_chimeric_e = check_criteria(*end_data)

    if non_chimeric_b and non_chimeric_e:
        return qseqid  # Return the sequence ID if it is non-chimeric
    else:
        return None  # Otherwise, return None

# Step 11: Main function to run the script
def main():
    print("Step 1: Cleaning directories...")
    clean_directory(output_dir_begin)
    clean_directory(output_dir_end)
    clean_directory(rescued_dir)

    print("Step 2: Checking for matching FASTA and BLAST result files...")
    valid_files = check_file_pairs(input_dir, blast_output_dir)
    
    print("Step 3: Filtering sequences based on BLAST results...")
    for base_name in valid_files:
        blast_file = os.path.join(blast_output_dir, f"{base_name}.txt")
        input_file = os.path.join(input_dir, f"{base_name}.fasta")
        
        nonchimeric_sequences = filter_sequences(blast_file)

        print(f"Step 4: Saving non-chimeric sequences for {base_name}...")
        save_nonchimeric_sequences(input_file, nonchimeric_sequences, rescued_dir)
        
        print(f"Step 5: Trimming sequences for {base_name}...")
        trim_sequences(input_file, output_dir_begin, output_dir_end, nonchimeric_sequences)
    
    print("Step 6: Running BLAST for begin and end directories...")
    for file_name in os.listdir(output_dir_begin):
        if file_name.endswith(".fasta"):
            print(f"Running BLAST for {file_name} in begin directory...")
            run_blast(os.path.join(output_dir_begin, file_name), db, header)
    
    for file_name in os.listdir(output_dir_end):
        if file_name.endswith(".fasta"):
            print(f"Running BLAST for {file_name} in end directory...")
            run_blast(os.path.join(output_dir_end, file_name), db, header)
    
    print("Step 7: Processing and identifying chimeric sequences...")
    all_nonchimeric_sequences = []

    for base_name in valid_files:
        blast_file = os.path.join(blast_output_dir, f"{base_name}.txt")
        input_file = os.path.join(input_dir, f"{base_name}.fasta")
        nonchimeric_sequences = filter_sequences(blast_file)

        for qseqid in nonchimeric_sequences:
            result = process_qseqid(qseqid)
            if result:
                all_nonchimeric_sequences.append(result)

    print(f"Non-chimeric sequences have been rescued and saved in {rescued_dir}")

if __name__ == "__main__":
    main()

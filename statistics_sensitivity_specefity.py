####The script is developed for finding out the specifity and senstivity rate of chimeras detected #####

import os

# Function to parse the chimera_info_file and store it in a dictionary
def parse_chimera_info(chimera_info_file):
    chimera_dict = {}
    with open(chimera_info_file, "r") as f:
        next(f)  # skip header
        for line in f:
            chimera_id, seq1_id, seq1_file, seq2_id, seq2_file, breakpoint, reversed_status, ratio, chimera_seq_length = line.strip().split("\t")
            chimera_dict[chimera_id] = (seq1_id, seq1_file, seq2_id, seq2_file, breakpoint, reversed_status, ratio, chimera_seq_length)
    return chimera_dict

# Function to parse the FASTA file of detected chimeric sequences and store the IDs in a set
def parse_detected_chimeras(fasta_file):
    detected_chimeras = set()
    with open(fasta_file, "r") as f:
        for record in SeqIO.parse(f, "fasta"):
            detected_chimeras.add(record.id.split(";")[0])  # Remove ";size=2" from the ID
    return detected_chimeras

# Function to calculate true positives, false positives, true negatives, and false negatives
def calculate_rates(chimera_dict, detected_chimeras, total_non_chimera_reads):
    true_positives = len(detected_chimeras.intersection(chimera_dict.keys()))
    false_positives = len(detected_chimeras.difference(chimera_dict.keys()))
    false_negatives = len(chimera_dict.keys()) - true_positives
    true_negatives = total_non_chimera_reads - false_positives

    return true_positives, false_positives, true_negatives, false_negatives

# Set the folder path where the FASTA files are located
folder_path = "/home/ali/Documents/simulated_data/analysis/UCHIME/reference/chimeric"

# List all the FASTA files in the folder
fasta_files = glob.glob(os.path.join(folder_path, "*.fasta"))

# Create an empty DataFrame to store the results
results_df = pd.DataFrame(columns=["File", "Generated Chimeras", "Detected Chimeras", "Proportion Detected", "True Positives", "False Positives", "True Negatives", "False Negatives", "Sensitivity", "Specificity"])

# Iterate over the FASTA files
for fasta_file in fasta_files:
    # Parse the chimera_info_file and detected_chimeras_fasta
    chimera_info_file = os.path.join(folder_path, "chimera_info.tsv")
    chimera_dict = parse_chimera_info(chimera_info_file)
    detected_chimeras = parse_detected_chimeras(fasta_file)

    # Compare the generated and detected chimeras
    match_count = 0
    for chimera_id in chimera_dict:
        if chimera_id in detected_chimeras:
            match_count += 1

    # Calculate the proportion of generated chimeras that were successfully detected
    proportion_detected = match_count / len(chimera_dict)

    #### Report generation ####

    total_non_chimera_reads = 44470  # Set this value to the number of non-chimera reads in dataset

    # Calculate rates
    tp, fp, tn, fn = calculate_rates(chimera_dict, detected_chimeras, total_non_chimera_reads)

    # Additional calculations based on the rates
    sensitivity = tp / (tp + fn)
    specificity = tn / (tn + fp)

    # Append the results to the DataFrame
    results_df = results_df.append({
        "File": os.path.basename(fasta_file),
        "Generated Chimeras": len(chimera_dict),
        "Detected Chimeras": match_count,
        "Proportion Detected": proportion_detected,
        "True Positives": tp,
        "False Positives": fp,
        "True Negatives": tn,
        "False Negatives": fn,
        "Sensitivity": sensitivity,
        "Specificity": specificity
    }, ignore_index=True)

# Save the results DataFrame as a TSV file
results_file = os.path.join(folder_path, "chimera_detection_results.tsv")
results_df.to_csv(results_file, sep="\t", index=False)

print("Report generation completed.")

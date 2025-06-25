# esp32-nvs-mod
A toolset for unpacking, modifying and recreating ESP32 NVS partitions

## Step 1 - Unpacking: nvs\_read.py

First we need to extract all the data contained in the NVS partition to a JSON format

```
python nvs_read.py nvs.bin data.json
```

## Step 2 - Convert to CSV format: generate\_nvs\_csv.py

Second we need to convert this JSON format to the [nvs\_partition\_gen.py CSV format](https://github.com/espressif/esp-idf/tree/master/components/nvs_flash/nvs_partition_generator)

```
python generate_nvs_csv.py data.json data.csv
```

## Step 3 - Modify key/value data

Edit the CSV file OR the blob data pointed to by a CSV entry

## Step 4 - Build new NVS partition

clone the esp-idf repo:
```
git clone https://github.com/espressif/esp-idf.git
```

generate nvs partition (assuming the original partition size is 16384)
```
./esp-idf/components/nvs_flash/nvs_partition_generator/nvs_partition_gen.py generate data.csv mod-nvs.bin 16384
```

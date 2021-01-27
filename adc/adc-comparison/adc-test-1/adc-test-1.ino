// adc-test-1 v1.0
// Print values from ADC to compare between boards
// Port of CircuitPython version intended for ESP boards


int input_pin = 4;  // GP4 on ESP32
unsigned int sample_sizes[] = {1, 8, 50};

int dummy_out_value = -1;

#define OUTPUT_LINE_LEN 80
char output_line[OUTPUT_LINE_LEN];  // not NUL terminated

#define TIME_FN() (micros() - program_start_time)
double time_mul = 1e-6;
unsigned long program_start_time = 0L;
unsigned long last_loop = 0L;
unsigned long interval = 25L * 1000L; // 25ms

#define SAMPLE_BITS 12
double cp_mul = 65535.0 / ((1 << SAMPLE_BITS) - 1);


void setup() {
    Serial.begin(115200);
    while (!Serial);  // wait for it to be ready

  // ESP32 defaults to 12bit -11dB
  // Some reports that 11bit has better performance >3.1V
  analogSetWidth(SAMPLE_BITS);
  analogReadResolution(SAMPLE_BITS);
  program_start_time = TIME_FN();

  delay(30 * 1000);  // 30 second pause before starting
}


void loop() {
  unsigned long now = 0L;
  // Wait for interval to pass
  // This will work for about 71 minutes which is good enough here
  while (1) {
    now = TIME_FN();
    if (now > last_loop + interval) break;
  }
  last_loop = now;

  for (int s_idx = 0; s_idx < sizeof(sample_sizes) / sizeof(sample_sizes[0]); s_idx++) {
    unsigned long in_start_t = TIME_FN();
    unsigned long sample_sum = 0L;
    for (int i=0; i < sample_sizes[s_idx]; i++) {
      sample_sum += analogRead(input_pin);
    }
    double in_value = (double)sample_sum / (double)sample_sizes[s_idx];
    snprintf(output_line,
             sizeof(output_line) / sizeof(output_line[0]),
             "%f,%d,%u,%f",
             (double)in_start_t * time_mul,
             dummy_out_value,
             sample_sizes[s_idx],
             in_value * cp_mul); // convert to 0-65535.0 range

    // Pad white whitespace but leave room for CRLF
    for (int i = strlen(output_line); i < (OUTPUT_LINE_LEN - 2) ; i++) {
      output_line[i] = ' ';
    }
    output_line[OUTPUT_LINE_LEN - 2 ] = '\r';  // CR
    output_line[OUTPUT_LINE_LEN - 2 ] = '\n';  // LF
    Serial.write(output_line, OUTPUT_LINE_LEN);
  }
}

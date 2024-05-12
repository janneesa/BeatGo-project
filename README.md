# BeatGo project - HR and HRV analysis device
<br />Heart rate and heart rate variability analysis device implemented using Raspberry Pi Pico W and Crowtail - Pulse Sensor.
<br />
<br />
<br /><b>Components:</b>
<ul>
      <li>Raspberry Pi Pico W</li>
      <li>Crowtail - Pulse Sensor V2.0</li>
      <li>OLED (SSD1306)</li>
      <li>Rotary knob</li>
</ul>
<br /><b>Methods:</b>
<ul>
      <li>Micropython</li>
      <li>Thonny IDE</li>
</ul>



<h2> Operating Principle </h2>
The Crowtail optical sensor connects to a Raspberry Pico Pi W to detect heart rate as an analog signal, which is then converted to digital using the microcontroller's AD-converter. 
The device uses proprietary algorithms to measure the peak-to-peak interval (PPI) of the heart signal. 
Various parameters like mean PPI, mean heart rate, SDNN, RMSSD, and Poincare plot shape parameters are analyzed using gathered interval data. 
Additionally, the PPI data is wirelessly transmitted to the Kubios Cloud Service for further analysis, which provides recovery and stress indexes. 
The results are displayed on an OLED screen, and a rotary knob allows user interaction for activities like initialization or restarting measurements.

<br /><b>Contributors:</b>
<ul>
      <li>@janneesa</li>
      <li>@mkksrl</li>
</ul>

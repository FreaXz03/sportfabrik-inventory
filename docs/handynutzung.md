# Mobile Usage – Planning

## Agreed plan for mobile usage – 2026-09-24

**Status: planning only. Implementation not until near the end of the project; no implementation now.** An exact date and where it fits relative to phases F/G are not yet set.

- **App form:** extend the existing Sportfabrik Inventory as a mobile-friendly web app, opened via a link and saved as an icon on the home screen. No separate native app or app-store release is planned.
- **Devices:** staff, branch managers', and management's personal phones; personal logins and existing roles/permissions stay in place.
- **Features:** search items or scan EAN/barcode with the phone camera; view price, size, color, and branch stock; count goods and correct stock; confirm goods receipts, transfer, and write off stock. Provide large, easy-to-use buttons.
- **Staff:** access only via the approved store Wi-Fi. No data access and no bookings from outside. "In the store" is determined by the allowed network access, not by GPS.
- **Branch managers and management/head office:** additionally protected access while out and about and from home, including over mobile data. External access does not extend existing editing rights.
- **Access protection:** the server must check network access and role; hidden UI controls alone are not enough. The concrete VPN solution, allowed Wi-Fi networks, and network segmentation are still to be defined; Tailscale is at most an example, not a decided solution.
- **Data and connection:** phone and PC use the same central database on the Sportfabrik server. A connection to the server is required from the start; offline bookings and later synchronization are not planned.
- **Later implementation:** first try out mobile search and camera scanning on Fabian's iPhone, then add the booking workflows and test on iPhone/Android. Test camera scanning with real labels; prevent unintended duplicate bookings of the same barcode.

Source: Fabian's confirmation in the conversation of 2026-09-24. This plan is not an order to build mobile usage now.

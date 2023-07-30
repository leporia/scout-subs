# 0.7 (30 jul 2023)
- Fix lazyload not working in Safari (iOS)
- Make archiving documents permanent
- Add BETA tables view for users and documents
- Users can manage multiple physical persons (Usercodes)
- Document list now only shows a single type, it can be accessed from the type
  list
- New compact count of documents by types diveded by branca
- Other bug fixes

# 0.6 (7 aug 2022)
- Merge the two pages for approving documents (bulk and uploading signature)
- Add QR code and barcodes to printed pdf approval document
- QR code/barcode scanner to approve documents faster
- Fix Chrome bug showing white pages
- Multiple user/user switcher
- New tips for enduser to approve document and go back to home page
- Fix data export problems and add user group to CSV export
- Quick filters for groups on document list

# 0.5 (21 jan 2022)
- Bug: users of other groups also visible in user list
- Show warning if some account fields are empty
- Implementation of oauth login using midata/hitobito
- New settings tab in profile page
- Password change
- Multiple choice for custom parameters

# 0.4 (23 set 2021)
- Bug: emergency document list visible also to non "capi"
- Overall performance improvements leveraging SQL queries

# 0.3 (23 jul 2021)

- Bug: Reconvert images to JPEG so that all device can show them
- Automatic concatenation of multiple uploaded images
- Downloading multiple documents as zip file
- Group "capi" with possibility to make documents only available to them
- Change of accent color and more modular visual design
- Automatically convert pdf to images when uploading
- Lazyload of images

# 0.2 (31 jul 2020)

- Bug: Dirty form detection now working
- Better mobile support
- Compress images to webp to use less space
- About page with licence
- Make non interactive item more obvious
- Terms and conditions checkbox and page
- Possibility to upload signed approvement document
- Possibility to controll a secondary group

# 0.1 (21 jul 2020)

- Filter documents and documents type
- Download documents
- Multi group support (secondary groups that are not "branche")
- Password reset

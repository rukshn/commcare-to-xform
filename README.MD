# XForms to XLSForm

**Still work in progress**

**There are still some elements that have not been fully converted**

This script tries to convert a COMMCARE XML file to a XForm / XLSForm/ ODK - file (XLSX) file to be used in CHT (Community health toolkit file)

### Problem

After designing a data collection form in CommCare, CHT, ODK, the platform gerenates an XForm which is based on XML standard.

Even though these platforms use the XLSForm files created using a spreadsheet software like MS Excel as an input, after creating the XForm, there is no way to convert it back to XLSForm from the XForm.

So if the creator of the XLS file is not available, or the XLS file is not avialable for whatever reason, the users effectively gets locked in to a platform and unable to migrate because the XLS file cannot be created from the XML File.

The form structure and logics are quite complex and since XLSForm is not a proper standard, and Excel not being an IDE, it is extreamely complex (but not impossible) task for humans to manually create these complex Excel sheets, without errors.

### XForms to XLSForm

This python script hopes to solve the issue by **trying** to convert the XForm XML file back to an XLSForm Excel file.

Effectively enabling countries and organizations to freely migrate between different data collection software like CommCare, CHT, ODK etc.

The python script won't be 100% acurate in converting, but it will be able to generate large portion of the file, where human editing can fix the minior issues in the final output of the python script.

### Usefull links

- CommCare form structure specification - https://dimagi.github.io/xform-spec/

### Updates

- First XLS to XLSX (Excel) was done on 22/02/2024 ⚛️ - But far from perfect.
- Ability to parse multiple languages | 23/02/2024

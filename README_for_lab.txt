CONNECT6 ENGINE -- LAB PC BUILD INSTRUCTIONS (Ubuntu)
=====================================================

You need ~10-15 minutes. Everything is offline except one pip install
(pyinstaller). No admin rights required.

STEPS
-----
1. Unzip this kit (connect6-build.zip) anywhere, e.g. Desktop.
2. Open a terminal in the unzipped folder (Connect6-build).
3. Run:

       cd Connect6Engine-master
       bash build.sh

4. At the end the script prints "DONE: OK" and "SMOKE TEST: PASS"
   if everything worked. It also plays one verification game against
   cloudict.linux automatically (takes a few minutes at most).

BRING BACK (from Connect6Engine-master/)
----------------------------------------
   - build_log.txt          (the full build record)
   - smoke_out.txt          (protocol output)
   - verify_match.txt       (game transcript, if the match ran)
   - dist/main              (the Linux executable -- THE DELIVERABLE)

WHILE YOU ARE THERE, PLEASE NOTE
-------------------------------
   - Ubuntu version:   lsb_release -a
   - Python version:   python3 --version
   - Is the course GUI installed on the lab PCs? Where?

IF SOMETHING FAILS
------------------
build_log.txt still contains everything needed to diagnose it --
just bring it back. Common cases:
   - "python3 not found": try python3.10/python3.11 explicitly,
     install location may differ.
   - pip blocked: report the error lines from the log.

Kit contents:
   Connect6Engine-master/   engine source + devtools + build.sh + verify.sh
   Connect6GUI-master/      teacher's GUI (used only for cloudict.linux
                             and the protocol wrapper -- nothing is modified)

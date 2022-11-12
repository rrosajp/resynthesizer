
'''
A script to test the resynthesizer.

Lloyd Konneker

Suite of test cases.
Most test cases are the plugins that call the resynthesizer engine plugin.
A few are direct calls to the resynthesizer engine.
Note the plugins must be installed, this calls them through the pdb.

Uses diff to compare output image with known good results (reference images).
Output is to a temp directory ( typically /tmp).

Result type enumeration:
FAILED: output does not match reference image
SUCCESS: does match
UNKNOWN: no reference image exists, one was created, manually judge the reference and run testsuite again
EXCEPTION: a called plugin threw a RuntimeError exception
IMPROPER: a test file could not be opened, or similar

Reference images are created on the first run.
Delete a reference image and run testsuite again to create a new reference image.
OR review the output in temp and if OK, paste it over the reference image.

Note this test only works on a build of the resynthesizer that is repeatable i.e. deterministic
especially its random seed.
You must build with /lib/buildswitches.h having "//#define SYNTH_THREADED TRUE" i.e. commented out.

Note that anytime you change the code (usually the engine)
so that the prng pseudo random number generator sequence is changed
this automated test will usually fail.
Then you must manually inspect the output files to ensure the result is as expected,
i.e. without glaring visual differences from the prior reference images.
Then you usually need to replace the entire set of reference images.

Invoke:
cd resynthesizer/Test
gimp -i --batch-interpreter python-fu-eval --batch - < testResynth.py

The test takes tens of minutes.  
Then review the log resynth-test.log.
The log has a summary at the end.  
Every test case should pass.
If you want to see the results in real time, use 'tail -f resynth-test.log'

Note the test saves PPM format because PPM format is large but repeatable,
whereas PNG is not repeatable because of timestamp.

Note that the test harness creates a new image from a file and 
saves the result image in a file separate from the input.
That is, the input images files proper are sacrosanct.

Note uses the logging module, mainly to avoid issues with print to stdout on some platforms.
'''



from gimpfu import *
from commands import getstatusoutput
import os
import time
import tempfile
import logging


# Set up file paths
testdir = './'

# put test results in a tmp directory (typically in /tmp)
tmpdir = tempfile.mkdtemp()

indir = f'{testdir}in_images/'
# For testing pure GIMP/glib with GRand: reference files different
referencedir = f'{testdir}reference_out_images/'
# For testing with stdc rand(): 
## referencedir = testdir + 'reference_out_images_rand/'

test_summary = ""

# selection rects
select1 = (100, 90, 100, 50)  # ufo
select2 = (90, 175, 135, 100) # donkey

def drawable_of_file(filename):
  '''
  Load a file and return the the drawable.
  A call to this can be used as an actual parameter, see instance below.
  '''
  image = pdb.gimp_file_load(filename, filename, run_mode=RUN_NONINTERACTIVE)
  pdb.gimp_image_flatten(image)
  return pdb.gimp_image_get_active_layer(image)

def drawable_of_file_with_anti_selection(filename, select):
  '''
  Load a file and return the the drawable.
  A call to this can be used as an actual parameter, see instance below.
  '''
  image = pdb.gimp_file_load(filename, filename, run_mode=RUN_NONINTERACTIVE)
  pdb.gimp_image_flatten(image)
  pdb.gimp_rect_select(image, select[0], select[1], select[2], select[3], 0, False, 0)
  pdb.gimp_selection_invert(image)
  return pdb.gimp_image_get_active_layer(image)

def record_test_result(testname, result, outfilename = ""):
  global test_summary
  logging.info(f"{result} {testname}")
  test_summary += f"{result} {testname} {outfilename}" + "\n"
  

def runtest(filename, testname, testcommand, testparameters, select=None):
  
  global test_summary
  
  logging.info("Running test " + testname)
  
  infilepath = indir + filename + '.png'
  # since some tests use the same input file, cat the testname to make an outfilename
  outfilename = testname + '-' + filename
  # out and reference have same name, different directories
  outfilepath = tmpdir + '/' + outfilename + '.ppm'
  referencefilepath = referencedir + '/' + outfilename + '.ppm'
  
  # open test file 
  try:
    image = pdb.gimp_file_load(infilepath, infilepath, run_mode=RUN_NONINTERACTIVE)
    drawable = pdb.gimp_image_get_active_layer(image)
    if select is not None:
      # Make selection    x,y, width, height
      # pdb.gimp_rect_select(image, 100, 90, 100, 50, 0, False, 0)
      pdb.gimp_rect_select(image, select[0], select[1], select[2], select[3], 0, False, 0)
  except:
    record_test_result(testname, "IMPROPER preprocessing")
    return
  
  # Build a test string
  teststring = testcommand + "(image, drawable," + testparameters + ",run_mode=RUN_NONINTERACTIVE)"
  logging.info("Test string:" + teststring)
  
  # Invoke the test
  # Formerly: eval(teststring) but eval only takes expressions, not statements
  start = time.time()
  try:
    exec teststring
  except RuntimeError:
    record_test_result(testname, "EXCEPTION")
    return
  logging.info("Elapsed time: " + str(time.time() - start))
  
  '''
  !!! Note that the test string can assign to image if the test returns a new image
  (rather than alter the image.)  Special handling here.
  '''
  logging.info("Test image name" + image.name)
  
  # test post processing
  try:
    # !!! Refresh drawable in case the plugin returned a new image
    drawable = pdb.gimp_image_get_active_drawable(image)
    
    # Save altered or new image in a temp directory.
    # !!! Why do you need to pass drawable, doesn't it save all the layers?  This bit me.
    if pdb.gimp_drawable_has_alpha(drawable) :
      pdb.gimp_image_flatten(image)   # Since saving ppm, get rid of alpha
      drawable = pdb.gimp_image_get_active_drawable(image)
    pdb.gimp_file_save(image, drawable, outfilepath, outfilepath, run_mode=RUN_NONINTERACTIVE)
    pdb.gimp_image_delete(image)
  except:
    record_test_result(testname, "IMPROPER post processing")
    return
  
  # If not reference out exists, make it (the first test run)
  if not os.path.exists(referencefilepath) :
    logging.debug("Making reference output image file.")
    status, output = getstatusoutput('cp ' + outfilepath + ' ' + referencefilepath)
    record_test_result(testname, "UNKNOWN ", outfilename)
    # test inconclusive, no reference data, must rerun
  else: 
    # diff reference image with recent image out
    status, output = getstatusoutput('diff ' + outfilepath + ' ' + referencefilepath)
  
    if status:  # !!! logic is reversed
      record_test_result(testname, "FAILED", outfilename)
    else:
      record_test_result(testname, "PASSED", outfilename)


def main():

  '''
  Run test cases for resynthesizer and plugins that call it.
  
  Notes on the test string:  optionally use names "image" and "drawable" to match the variable names used
  in the runtest() function; the names will be eval'ed.
  '''
  
  # Open the log
  LOG_FILENAME = 'resynth-test.log'
  logging.basicConfig(filename=LOG_FILENAME,level=logging.DEBUG)

  logging.info(f"Temp directory: {tmpdir}")

  # Make paths to various input files
  grasspath = f'{indir}grass-input-alpha.png'
  brickpath = f'{indir}brick.png'
  donkeypath = f'{indir}donkey_original.png'
  angelpath = f'{indir}angel_texture.png'
  wanderpath = f'{indir}wander-texture.png'
  zappath = f'{indir}zap-texture.png'
  ufopath = f'{indir}ufo-input.png'
    

  # Begin test definitions

  '''
  Straight resynthesis tests (without using a helper plugin, just resynth)
  '''

  # Resynthesis of small file from full context
  test = "pdb.plug_in_resynthesizer"
  # !!! Note we want the ID of the drawable
  parameters = "0,0, True, drawable_of_file_with_anti_selection('"+ zappath + "', select1).ID, -1, -1, 0.0, 0.117, 16, 500"
  runtest('zap-texture', 'resynthfull', test, parameters, select1)

  # Resynthesis of ufo from full context
  test = "pdb.plug_in_resynthesizer"
  # !!! Note we want the ID of the drawable
  parameters = "0,0, True, drawable_of_file_with_anti_selection('"+ ufopath + "', select1).ID, -1, -1, 0.0, 0.117, 16, 500"
  runtest('ufo-input', 'resynthfull', test, parameters, select1)

  # Resynthesis of rect selection in bricks from full context
  test = "pdb.plug_in_resynthesizer"
  # !!! Note we want the ID of the drawable
  parameters = "0,0, True, drawable_of_file_with_anti_selection('"+ brickpath + "', select1).ID, -1, -1, 0.0, 0.117, 16, 500"
  runtest('brick', 'resynthfull', test, parameters, select1)

  # Resynthesis of rect selection in donkey from full context
  test = "pdb.plug_in_resynthesizer"
  # !!! Note we want the ID of the drawable
  parameters = "0,0, True, drawable_of_file_with_anti_selection('"+ donkeypath + "', select2).ID, -1, -1, 0.0, 0.117, 16, 500"
  runtest('donkey_original', 'resynthfull', test, parameters, select2)

  '''
  Tests of mapping using helper plugins.
  '''
  # Texture transfer (map style) with texture having alpha
  # map style: RGBA to RGB w/ color maps

  test = "pdb.python_fu_map_style"
  parameters = "drawable_of_file('"+ grasspath + "'), 50.0, 0"
  # source image, fifty percent transfer, map by colors
  runtest('ufo-input', 'mapstylealpha', test, parameters, select=None)

  # Texture transfer (map style) with target having alpha
  # map style: RGB to RGBA w/ color maps
  # TODO this is not a test of the resynth since the plug-in is adding an alpha to texture
  test = "pdb.python_fu_map_style"
  parameters = "drawable_of_file('"+ grasspath + "'), 50.0, 0"
  # source image, fifty percent transfer, map by colors
  runtest('ufo-input-w-alpha', 'mapstyletoalpha', test, parameters, select=None)

  # Texture transfer (map style)
  # map style: RGB to RGB w/ color maps
  test = "pdb.python_fu_map_style"
  parameters = "drawable_of_file('"+ grasspath + "'), 50.0, 0"
  # source image, fifty percent transfer, map by colors
  runtest('ufo-input', 'mapstyle', test, parameters, select=None)

  # map style: RGB to RGB w/ color maps
  # This is conceptually little different from the above test, but it is a popular example.
  test = "pdb.python_fu_map_style"
  parameters = "drawable_of_file('"+ angelpath + "'), 10.0, 0"
  # source image, fifty percent transfer, map by colors
  runtest('angel_target', 'mapstyleangel', test, parameters, select=None)

  # map style: RGB to RGB w/ GRAY maps
  test = "pdb.python_fu_map_style"
  parameters = "drawable_of_file('"+ grasspath + "'), 50.0, 1"
  # source image, fifty percent transfer, map by brightness
  runtest('ufo-input', 'mapstylebrightness', test, parameters, select=None)

  # mapstyle: GRAY to GRAY
  test = "pdb.python_fu_map_style"
  parameters = "drawable_of_file('"+ wanderpath + "'), 50.0, 0"
  # source image, fifty percent transfer, map by colors
  runtest('wander', 'mapstylegraygray', test, parameters, select=None)

  # mapstyle: RGB to GRAY
  test = "pdb.python_fu_map_style"
  parameters = "drawable_of_file('"+ zappath + "'), 10.0, 0"
  # source image, ten percent transfer, map by colors
  runtest('zap-output-map', 'mapstylergbgray', test, parameters, select=None)

  # Render texture
  # !!! Note here the plugin returns a new image which we assign to image variable
  test = "image = pdb.python_fu_render_texture"
  parameters = "2, 1"
  runtest('grass-input', 'rendertexture', test, parameters, select=None)

  # Render texture w alpha yields a new image that has alpha channel but pixels are all opaque
  # !!! Note here the plugin returns a new image which we assign to image variable
  test = "image = pdb.python_fu_render_texture"
  parameters = "2, 1"
  runtest('grass-input-alpha', 'rendertexturealpha', test, parameters, select=None)

  '''
  More straight resynthesis tests.
  '''

  # Straight resynthesis, from selection in drawable into same selection in drawable
  # !!! Note the target image is not in this parameter string, it is the corpus.
  test = "pdb.plug_in_resynthesizer"
  parameters = "0,0, True, drawable.ID, -1, -1, 0.0, 0.117, 16, 500"
  runtest('ufo-input', 'resynth', test, parameters, select1)

  # Straight resynthesis, from separate image with no selection into selection in drawable
  test = "pdb.plug_in_resynthesizer"
  # !!! Note we want the ID of the drawable
  parameters = "0,0, True, drawable_of_file('"+ grasspath + "').ID, -1, -1, 0.0, 0.117, 16, 500"
  runtest('ufo-input', 'resynthtwoimages', test, parameters, select1)

  # Straight resynthesis, from separate image with no selection into selection in drawable
  # also, tileable without using context: 1,1,0,...
  test = "pdb.plug_in_resynthesizer"
  # !!! Note we want the ID of the drawable
  parameters = "1, 1, 0, drawable_of_file('"+ grasspath + "').ID, -1, -1, 0.0, 0.117, 16, 500"
  runtest('ufo-input', 'resynthtileable', test, parameters, select1)

  '''
  Heal selection plugin tests.
  '''
  # Heal from donut corpus
  test = "pdb.python_fu_heal_selection"
  parameters = "50, 1, 1" # 1 = sample from sides, 1 = direction inward
  runtest('ufo-input', 'heal', test, parameters, select1)

  # Heal from donut corpus
  # also randomly all around
  test = "pdb.python_fu_heal_selection"
  parameters = "50, 0, 0" # 0 = sample from all around, 0 = randomly
  runtest('ufo-input', 'healaroundrandom', test, parameters, select1)

  # Heal where target includes alpha layer.
  # This selects from an area having a transparent area.
  # The transparent area should NOT be resynthesized, but yield white upon flattening.
  test = "pdb.python_fu_heal_selection"
  parameters = "50, 1, 1"
  runtest('ufo-input-w-alpha', 'healincludedalpha', test, parameters, select1)

  # Heal where target has distant alpha layer.
  # This selects from a black sky area with a nearby transparent area.
  # The result should be black resynthesized, NOT white of transparent flattened.
  test = "pdb.python_fu_heal_selection"
  parameters = "50, 1, 1"
  runtest('apollo11_w_alpha', 'healalpha', test, parameters, select1)

  # Heal a grayscale
  test = "pdb.python_fu_heal_selection"
  parameters = "50, 1, 1"
  runtest('wander', 'healgray', test, parameters, select1)

  # Heal a grayscale w alpha
  test = "pdb.python_fu_heal_selection"
  parameters = "50, 0, 1"
  runtest('ufo-input-w-alpha-gray', 'healalphagray', test, parameters, select1)

  # Heal transparency outward
  test = "pdb.python_fu_heal_transparency"
  parameters = "50, 2" # pixels of context width, outward
  runtest('apollo11_w_alpha', 'healtransparency', test, parameters, select=None)

  # Heal transparency inward
  test = "pdb.python_fu_heal_transparency"
  parameters = "50, 1" # pixels of context width, 1=inward
  runtest('apollo11_w_alpha', 'healtransparencyinward', test, parameters, select=None)

  '''
  Other plugin tests
  '''

  # Sharpen with resynthesis
  ''' Too slow to test regularly '''
  '''
  test = "pdb.python_fu_sharpen_resynthesized"
  parameters = "2"
  runtest('ufo-input', 'sharpen', test, parameters, select=None)
  '''

  # Uncrop 20%
  test = "pdb.python_fu_uncrop"
  parameters = "20"
  runtest('ufo-input', 'uncrop', test, parameters, select=None)

  # Fill resynthesized pattern
  test = "pdb.python_fu_fill_pattern_resynth"
  parameters = " 'Maple Leaves' "
  runtest('ufo-input', 'fillpattern', test, parameters, select1)

  # Enlarge with resynthesis
  # Enlarge factor = 2
  # !!! Very slow
  ''' Too slow to test regularly '''
  '''
  test = "pdb.python_fu_enlarge_resynthesized"
  parameters = "2"
  runtest('ufo-input-small', 'enlarge', test, parameters, select=None)
  '''





  # TODO a much harder test with many layers and alpha channels

  logging.info("\nTemp directory: " + tmpdir)
  logging.info( "\n" + test_summary)

  pdb.gimp_quit(True)
  
main()

#!/usr/bin/perl
#
# netlogo2R.pl
#
# Gary Polhill, 5 April 2012
#
# Create a single R-compatible CSV file from multiple netlogo output files

use FindBin;
use lib $FindBin::Bin;

use nlogo2R;

my $sep;
my $metadata = 0;

while($ARGV[0] =~ /^-/) {
  my $opt = shift(@ARGV);

  if($opt eq '-sep') {
    $sep = shift(@ARGV);
  }
  elsif($opt eq '-metadata') {
    $metadata = 1;
  }
  else {
    die "Unrecognised option: $opt\n";
  }
}

if(scalar(@ARGV) < 2) {
  die "Usage: $0 [-sep] <R file> <netlogo output files...>\n";
}

my $Rfile = shift(@ARGV);

my @nfiles = @ARGV;

nlogo2R::nlogo2R(@nfiles, $Rfile, $metadata, $sep);

exit 0;
